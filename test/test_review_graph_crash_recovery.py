from collections import Counter
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda

from extraction.html import HtmlDocumentExtractor
from graph.research_graph import create_research_graph
from persistence.database import SessionLocal
from test_search_result_fencing import create_session, expire_lease
from test_review_completion_fencing import acquire_lease
from test_review_selection_fencing import set_session_status
from test_research_graph_crash_recovery import prepare
from test_research_graph_pause_resume import (
    QUESTIONS, QUERIES, URLS, TwoQuestionSearch, TwoQuestionRetriever,
    session_status, question_rows, count_rows, count_findings,
)
from test_review_graph_pause_resume import (
    ReviewPauseModel, review_rows, support_rows,
)
from test_review_graph_integration import cleanup_reviews, rows, invoke
from test_research_graph_integration import cleanup_graph_test_session


class InjectedReviewCrash(RuntimeError):
    """Deliberate failure injected before persisting the second review."""


class CrashOnceReviewModel(ReviewPauseModel):
    def __init__(self, session_id):
        super().__init__(session_id)
        self.crash_enabled = True
        self.crash_count = 0
        self.review_pause_requested = True  # No cooperative pause in this test.

    def with_structured_output(self, schema, **kwargs):
        runnable = super().with_structured_output(schema, **kwargs)
        if schema.__name__ != "ResearchQuestionReview":
            return runnable

        def respond(messages):
            content = "\n".join(str(m.content) for m in messages)
            if self.crash_enabled and QUESTIONS[1] in content:
                self.crash_enabled = False
                self.crash_count += 1
                print("Injected worker crash during second review invocation.")
                raise InjectedReviewCrash("Simulated review worker crash")
            return runnable.invoke(messages)

        return RunnableLambda(respond)


def make_graph(model, search, retriever):
    models = SimpleNamespace(
        planner=model, researcher=model, summariser=model,
        reviewer=model, reporter=model, controller=model,
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
    print("REVIEW GRAPH CRASH RECOVERY")
    print("===========================")

    try:
        session_id = create_session()
        print(f"Disposable session: {session_id}")
        set_session_status(session_id, "created")
        model = CrashOnceReviewModel(session_id)
        search = TwoQuestionSearch()
        retriever = TwoQuestionRetriever()
        graph = make_graph(model, search, retriever)

        initial_lease = acquire_lease(session_id)
        prepare(session_id, initial_lease, resume=False)
        print("TEST 1 - Two-question fixture prepared: PASSED")

        invoke(graph, session_id, initial_lease, resume=False, target="research")
        questions = question_rows(session_id)
        assert len(questions) == 2, questions
        assert session_status(session_id) == "researched"
        assert [q.status for q in questions] == ["researched", "researched"]
        findings = rows("""
            SELECT q.id AS question_id, f.id AS finding_id
            FROM dbo.findings f
            JOIN dbo.research_questions q ON q.id = f.research_question_id
            WHERE q.research_session_id = :session_id
            ORDER BY q.id, f.id
        """, session_id=session_id)
        assert len(findings) == 2, findings
        for i, question in enumerate(questions):
            assert findings[i].question_id == question.id
            model.finding_ids[i] = findings[i].finding_id
        print("TEST 2 - Research completed and evidence persisted: PASSED")

        expire_lease(session_id)
        review_lease = acquire_lease(session_id)
        prepare(session_id, review_lease, resume=True)
        print("TEST 3 - Review worker prepared: PASSED")

        caught = None
        try:
            invoke(graph, session_id, review_lease, resume=True, target="review")
        except InjectedReviewCrash as exc:
            caught = exc
            print(f"Simulated worker interruption: {exc}")
        assert caught is not None, "Expected injected failure to escape graph.invoke"
        assert model.crash_count == 1
        print("TEST 4 - Worker interrupted during second review: PASSED")

        assert session_status(session_id) == "reviewing"
        assert [q.status for q in question_rows(session_id)] == [
            "reviewed", "reviewing"
        ], question_rows(session_id)
        first_reviews = review_rows(session_id)
        assert len(first_reviews) == 1, first_reviews
        assert first_reviews[0].research_question_id == questions[0].id
        assert [tuple(r) for r in support_rows(session_id)] == [
            (questions[0].id, model.finding_ids[0])
        ]
        print("TEST 5 - First review durable; interrupted review absent: PASSED")

        expire_lease(session_id)
        replacement_lease = acquire_lease(session_id)
        assert replacement_lease.version != review_lease.version
        prepare(session_id, replacement_lease, resume=True)
        print("TEST 6 - Replacement worker prepared: PASSED")

        invoke(graph, session_id, replacement_lease, resume=True, target="review")
        assert session_status(session_id) == "reviewed"
        assert [q.status for q in question_rows(session_id)] == [
            "reviewed", "reviewed"
        ]
        print("TEST 7 - Remaining review recovered and completed: PASSED")

        final_reviews = review_rows(session_id)
        assert len(final_reviews) == 2, final_reviews
        assert final_reviews[0].id == first_reviews[0].id
        assert [r.research_question_id for r in final_reviews] == [
            q.id for q in questions
        ]
        assert [tuple(r) for r in support_rows(session_id)] == [
            (questions[i].id, model.finding_ids[i]) for i in range(2)
        ]
        print("TEST 8 - No duplicate reviews or finding references: PASSED")

        assert search.calls == list(QUERIES), search.calls
        assert retriever.calls == list(URLS), retriever.calls
        assert count_rows("search_attempts", session_id) == 2
        assert count_rows("web_search_results", session_id) == 2
        assert count_rows("sources", session_id) == 2
        assert count_findings(session_id) == 2
        assert model.calls == Counter({
            "ResearchPlan": 1, "SearchPlan": 2,
            "SourceAnalysis": 2, "ResearchQuestionReview": 2,
        }), model.calls
        assert model.crash_count == 1
        print("TEST 9 - Research not repeated; review only retried as necessary: PASSED")
        print("\nPASS")

    finally:
        if session_id is not None:
            try:
                cleanup_reviews(session_id)
            finally:
                cleanup_graph_test_session(session_id)


if __name__ == "__main__":
    main()
