from collections import Counter
from types import SimpleNamespace

from sqlalchemy import text

from extraction.html import HtmlDocumentExtractor
from graph.research_graph import create_research_graph
from persistence.database import SessionLocal
from persistence.research_session_repository import ResearchSessionRepository

from test_search_result_fencing import create_session, expire_lease
from test_review_completion_fencing import acquire_lease
from test_review_selection_fencing import set_session_status
from test_research_graph_integration import (
    FakeStructuredChatModel,
    FakeSearchProvider,
    FakeDocumentRetriever,
    TEST_URL,
)
from test_research_graph_pause_resume import (
    cleanup_graph_test_session,
    session_status,
    question_rows,
    count_rows,
    count_findings,
)


class SimulatedWorkerCrash(BaseException):
    """Bypass ordinary per-document `except Exception` recovery."""


class CrashOnceRetriever(FakeDocumentRetriever):
    def __init__(self):
        super().__init__()
        self.crash_pending = True

    def retrieve(self, url):
        if self.crash_pending:
            self.crash_pending = False
            self.calls.append(url)
            raise SimulatedWorkerCrash(
                "Simulated worker crash immediately before document retrieval"
            )
        return super().retrieve(url)


def state(session_id, resume):
    return {
        "session_id": session_id,
        "topic": "Deterministic graph integration test",
        "scope": None,
        "resume": resume,
        "resume_phase": None,
        "execution_target": "research",
        "pause_requested": False,
        "research_plan": None,
        "current_question_id": None,
        "current_question": None,
        "search_required": True,
        "current_search_attempt_id": None,
        "search_plan": None,
        "search_results": [],
        "current_review_question_id": None,
        "current_review_question": None,
    }


def invoke(graph, session_id, lease, resume):
    return graph.invoke(
        state(session_id, resume),
        config={
            "configurable": {"execution_lease": lease},
            "recursion_limit": 100,
        },
    )


def prepare(session_id, lease, resume):
    with SessionLocal() as db:
        ResearchSessionRepository(db).prepare_execution_fenced(
            session_id=session_id,
            lease=lease,
            resume=resume,
        )


def get_search_attempts(session_id):
    with SessionLocal() as db:
        return db.execute(
            text(
                "SELECT id, status FROM dbo.search_attempts "
                "WHERE research_session_id = :session_id ORDER BY id"
            ),
            {"session_id": session_id},
        ).all()


def main():
    session_id = None
    print("RESEARCH GRAPH CRASH RECOVERY")
    print("=============================")

    try:
        session_id = create_session()
        print(f"Disposable session: {session_id}")
        set_session_status(session_id, "created")

        first_lease = acquire_lease(session_id)
        prepare(session_id, first_lease, resume=False)
        assert session_status(session_id) == "planning"
        print("TEST 1 - Initial execution prepared: PASSED")

        model = FakeStructuredChatModel()
        search = FakeSearchProvider()
        retriever = CrashOnceRetriever()
        models = SimpleNamespace(
            planner=model,
            researcher=model,
            summariser=model,
            reviewer=model,
            reporter=model,
            controller=model,
        )
        graph = create_research_graph(
            models=models,
            session_factory=SessionLocal,
            search_provider=search,
            document_retriever=retriever,
            document_extractor=HtmlDocumentExtractor(),
        )

        try:
            invoke(graph, session_id, first_lease, resume=False)
        except SimulatedWorkerCrash as exc:
            print(f"Injected interruption: {exc}")
        else:
            raise AssertionError("Expected simulated crash did not propagate")
        print("TEST 2 - Worker interrupted during retrieval: PASSED")

        # The search must already be committed, while no source/analysis
        # has been persisted and the active question remains in progress.
        assert session_status(session_id) == "researching"
        questions = question_rows(session_id)
        assert len(questions) == 1, questions
        assert questions[0].status == "researching", questions
        attempts = get_search_attempts(session_id)
        assert len(attempts) == 1, attempts
        assert attempts[0].status == "completed", attempts
        assert count_rows("search_attempts", session_id) == 1
        assert count_rows("web_search_results", session_id) == 1
        assert count_rows("sources", session_id) == 0
        assert count_findings(session_id) == 0
        assert len(search.calls) == 1, search.calls
        assert model.calls == Counter({"ResearchPlan": 1, "SearchPlan": 1})
        print("TEST 3 - Partial progress durable and consistent: PASSED")

        # Simulate lease expiry while the original worker is gone.
        # The helper accepts a session_id string, not an ExecutionLease.
        expire_lease(session_id)
        replacement_lease = acquire_lease(session_id)
        assert replacement_lease.version != first_lease.version
        prepare(session_id, replacement_lease, resume=True)
        assert session_status(session_id) == "researching"
        print("TEST 4 - Replacement lease prepared: PASSED")

        result = invoke(graph, session_id, replacement_lease, resume=True)
        assert isinstance(result, dict)
        assert session_status(session_id) == "researched"
        assert [q.status for q in question_rows(session_id)] == ["researched"]
        print("TEST 5 - Graph recovered and completed research: PASSED")

        # Search should not run again. Retrieval is attempted twice:
        # first invocation crashes, second successfully retrieves.
        assert len(search.calls) == 1, search.calls
        assert retriever.calls == [TEST_URL, TEST_URL], retriever.calls
        assert model.calls == Counter(
            {"ResearchPlan": 1, "SearchPlan": 1, "SourceAnalysis": 1}
        ), model.calls
        print("TEST 6 - Search and planning not repeated: PASSED")

        assert count_rows("search_attempts", session_id) == 1
        assert count_rows("web_search_results", session_id) == 1
        assert count_rows("sources", session_id) == 1
        assert count_findings(session_id) == 1
        print("TEST 7 - No duplicate persisted records: PASSED")
        print("\nPASS")

    finally:
        if session_id is not None:
            cleanup_graph_test_session(session_id)
            # The shared cleanup helper prints its own success message.


if __name__ == "__main__":
    main()
