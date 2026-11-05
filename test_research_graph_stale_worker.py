"""Stale-worker fencing through the production research graph.

Run beside existing tests:
    python test_research_graph_stale_worker.py

Uses real SQL Server repositories and LangGraph, fake LLM/search/retrieval.
The lease is superseded synchronously during source analysis, immediately
before the old worker attempts to persist its generated findings.
"""

from collections import Counter
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda
from sqlalchemy import text

from extraction.html import HtmlDocumentExtractor
from graph.research_graph import create_research_graph
from persistence.database import SessionLocal
from test_search_result_fencing import create_session, expire_lease
from test_review_completion_fencing import acquire_lease
from test_review_selection_fencing import set_session_status
from test_research_graph_integration import (
    FakeStructuredChatModel,
    FakeSearchProvider,
    FakeDocumentRetriever,
    cleanup_graph_test_session,
)
from test_research_graph_crash_recovery import (
    prepare,
    invoke,
    get_search_attempts,
)
from test_research_graph_pause_resume import (
    session_status,
    question_rows,
    count_rows,
    count_findings,
)


class LeaseSupersedingModel(FakeStructuredChatModel):
    """Supersede worker A after inference but before finding persistence."""

    def __init__(self, session_id):
        super().__init__()
        self.session_id = session_id
        self.supersede_once = True
        self.replacement_lease = None
        self.old_lease = None

    def with_structured_output(self, schema, **kwargs):
        base = super().with_structured_output(schema, **kwargs)

        if schema.__name__ != "SourceAnalysis":
            return base

        def respond(messages):
            result = base.invoke(messages)

            if self.supersede_once:
                self.supersede_once = False

                # The old graph still holds the old lease in RunnableConfig.
                # Force expiry and replace ownership before it attempts
                # FindingRepository.save_analysis(..., lease=old_lease).
                expire_lease(self.session_id)
                self.replacement_lease = acquire_lease(self.session_id)
                assert self.replacement_lease.version != self.old_lease.version
                print(
                    "Injected lease supersession during source analysis: "
                    f"version {self.old_lease.version} -> "
                    f"{self.replacement_lease.version}"
                )

            return result

        return RunnableLambda(respond)


def make_graph(model, search, retriever):
    models = SimpleNamespace(
        planner=model,
        researcher=model,
        summariser=model,
        reviewer=model,
        reporter=model,
        controller=model,
    )
    return create_research_graph(
        models=models,
        session_factory=SessionLocal,
        search_provider=search,
        document_retriever=retriever,
        document_extractor=HtmlDocumentExtractor(),
    )


def main():
    session_id = None
    print("RESEARCH GRAPH STALE-WORKER FENCING")
    print("===================================")

    try:
        session_id = create_session()
        print(f"Disposable session: {session_id}")
        set_session_status(session_id, "created")

        old_lease = acquire_lease(session_id)
        prepare(session_id, old_lease, resume=False)
        assert session_status(session_id) == "planning"
        print("TEST 1 - Initial worker prepared: PASSED")

        model = LeaseSupersedingModel(session_id)
        model.old_lease = old_lease
        search = FakeSearchProvider()
        retriever = FakeDocumentRetriever()
        graph = make_graph(model, search, retriever)

        # Some production nodes deliberately re-raise fencing failures;
        # others may catch ordinary exceptions. Either way, a stale graph
        # must not complete the session or persist a finding.
        stale_error = None
        try:
            invoke(graph, session_id, old_lease, resume=False)
        except Exception as exc:
            stale_error = exc
            print(f"Stale worker rejected: {type(exc).__name__}: {exc}")

        assert model.replacement_lease is not None, (
            "Test did not reach the lease-supersession injection point."
        )
        print("TEST 2 - Lease superseded during analysis: PASSED")

        assert stale_error is not None, (
            "Stale worker returned normally; inspect whether a fence failure "
            "was swallowed by an exception handler."
        )
        print("TEST 3 - Stale worker rejected: PASSED")

        assert session_status(session_id) == "researching"
        questions = question_rows(session_id)
        assert len(questions) == 1 and questions[0].status == "researching", questions
        assert count_rows("search_attempts", session_id) == 1
        assert count_rows("web_search_results", session_id) == 1
        assert count_rows("sources", session_id) == 1
        assert count_findings(session_id) == 0, (
            "Stale worker persisted a finding despite losing its lease."
        )
        assert len(search.calls) == 1
        assert len(retriever.calls) == 1
        print("TEST 4 - Stale write rejected without partial persistence: PASSED")

        # Worker B uses its new lease to recover the same question.
        replacement_lease = model.replacement_lease
        prepare(session_id, replacement_lease, resume=True)
        assert session_status(session_id) == "researching"
        print("TEST 5 - Replacement worker prepared: PASSED")

        result = invoke(graph, session_id, replacement_lease, resume=True)
        assert isinstance(result, dict)
        assert session_status(session_id) == "researched"
        assert [q.status for q in question_rows(session_id)] == ["researched"]
        print("TEST 6 - Replacement worker completed research: PASSED")

        assert count_rows("search_attempts", session_id) == 1
        assert count_rows("web_search_results", session_id) == 1
        assert count_rows("sources", session_id) == 1
        assert count_findings(session_id) == 1
        assert len(search.calls) == 1, search.calls
        assert len(retriever.calls) == 1, retriever.calls
        assert model.calls == Counter(
            {"ResearchPlan": 1, "SearchPlan": 1, "SourceAnalysis": 2}
        ), model.calls
        print("TEST 7 - No duplicate search, retrieval or persisted findings: PASSED")
        print("\nPASS")

    finally:
        if session_id is not None:
            cleanup_graph_test_session(session_id)


if __name__ == "__main__":
    main()
