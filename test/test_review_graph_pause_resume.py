from collections import Counter
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda
from sqlalchemy import text

from domain.review import ResearchQuestionReview
from extraction.html import HtmlDocumentExtractor
from graph.research_graph import create_research_graph
from persistence.database import SessionLocal
from test_search_result_fencing import create_session, expire_lease
from test_review_completion_fencing import acquire_lease
from test_review_selection_fencing import set_session_status
from test_research_graph_crash_recovery import prepare
from test_research_graph_pause_resume import (
    TOPIC, QUESTIONS, QUERIES, URLS,
    PauseAwareModel, TwoQuestionSearch, TwoQuestionRetriever,
    set_pause, session_status, question_rows, count_rows, count_findings,
)
from test_review_graph_integration import cleanup_reviews, rows, invoke
from test_research_graph_integration import cleanup_graph_test_session


class ReviewPauseModel(PauseAwareModel):
    """Two-question research fixture plus a pause after the first review."""

    def __init__(self, session_id):
        super().__init__(session_id)
        # Disable research-phase pause: only the review phase should pause.
        self.paused_once = True
        self.review_pause_requested = False
        self.finding_ids = {}

    def with_structured_output(self, schema, **kwargs):
        if schema.__name__ != "ResearchQuestionReview":
            return super().with_structured_output(schema, **kwargs)

        def respond(messages):
            self.calls["ResearchQuestionReview"] += 1
            content = "\n".join(str(m.content) for m in messages)
            matches = [i for i, question in enumerate(QUESTIONS) if question in content]
            assert len(matches) == 1, (
                "Could not identify the review question in model input: "
                f"matches={matches}"
            )
            i = matches[0]
            finding_id = self.finding_ids[i]

            # Request a durable pause while reviewing the first question.
            # The graph should finish persisting this review, then stop at
            # its review-phase pause boundary.
            if i == 0 and not self.review_pause_requested:
                set_pause(self.session_id, True)
                self.review_pause_requested = True
                print("Injected pause during first review model invocation.")

            return ResearchQuestionReview.model_validate({
                "answer": f"Controlled evidence supports question {i + 1}.",
                "overall_confidence": "high",
                "sufficient_evidence": True,
                "reviewed_claims": [{
                    "claim": f"Controlled evidence marker {i + 1} is present.",
                    "confidence": "high",
                    "supporting_finding_ids": [finding_id],
                    "contradicting_finding_ids": [],
                }],
                "contradictions": [],
                "evidence_gaps": [],
            })

        return RunnableLambda(respond)


def review_rows(session_id):
    return rows("""
        SELECT qr.id, qr.research_question_id, qr.answer
        FROM dbo.question_reviews qr
        JOIN dbo.research_questions q ON q.id = qr.research_question_id
        WHERE q.research_session_id = :session_id
        ORDER BY q.id
    """, session_id=session_id)


def support_rows(session_id):
    return rows("""
        SELECT qr.research_question_id, s.finding_id
        FROM dbo.reviewed_claim_support s
        JOIN dbo.reviewed_claims c ON c.id = s.reviewed_claim_id
        JOIN dbo.question_reviews qr ON qr.id = c.question_review_id
        JOIN dbo.research_questions q ON q.id = qr.research_question_id
        WHERE q.research_session_id = :session_id
        ORDER BY qr.research_question_id
    """, session_id=session_id)


def main():
    session_id = None
    print("REVIEW GRAPH PAUSE / RESUME")
    print("===========================")

    try:
        session_id = create_session()
        print(f"Disposable session: {session_id}")
        set_session_status(session_id, "created")

        model = ReviewPauseModel(session_id)
        search = TwoQuestionSearch()
        retriever = TwoQuestionRetriever()
        models = SimpleNamespace(
            planner=model, researcher=model, summariser=model,
            reviewer=model, reporter=model, controller=model,
        )
        graph = create_research_graph(
            models=models,
            session_factory=SessionLocal,
            search_provider=search,
            document_retriever=retriever,
            document_extractor=HtmlDocumentExtractor(),
        )
        first_lease = acquire_lease(session_id)
        prepare(session_id, first_lease, resume=False)
        print("TEST 1 - Two-question fixture prepared: PASSED")

        invoke(graph, session_id, first_lease, resume=False, target="research")
        assert session_status(session_id) == "researched"
        questions = question_rows(session_id)
        assert len(questions) == 2, questions
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

        assert model.calls == Counter({
            "ResearchPlan": 1, "SearchPlan": 2, "SourceAnalysis": 2,
        }), model.calls
        assert search.calls == list(QUERIES), search.calls
        assert retriever.calls == list(URLS), retriever.calls
        print("TEST 2 - Both research questions completed: PASSED")

        expire_lease(session_id)
        review_lease = acquire_lease(session_id)
        assert review_lease.version != first_lease.version
        prepare(session_id, review_lease, resume=True)
        print("TEST 3 - Review execution lease prepared: PASSED")

        first_result = invoke(
            graph, session_id, review_lease, resume=True, target="review"
        )
        assert isinstance(first_result, dict)
        assert first_result.get("pause_requested") is True, first_result
        assert session_status(session_id) == "reviewing"
        assert [q.status for q in question_rows(session_id)] == [
            "reviewed", "researched"
        ], question_rows(session_id)
        print("TEST 4 - Review paused after first completed question: PASSED")

        first_reviews = review_rows(session_id)
        assert len(first_reviews) == 1, first_reviews
        assert first_reviews[0].research_question_id == questions[0].id
        assert [tuple(r) for r in support_rows(session_id)] == [
            (questions[0].id, model.finding_ids[0])
        ]
        assert model.calls["ResearchQuestionReview"] == 1, model.calls
        print("TEST 5 - First review and finding reference persisted once: PASSED")

        set_pause(session_id, False)
        expire_lease(session_id)
        replacement_lease = acquire_lease(session_id)
        assert replacement_lease.version != review_lease.version
        prepare(session_id, replacement_lease, resume=True)
        print("TEST 6 - Replacement worker prepared: PASSED")

        second_result = invoke(
            graph, session_id, replacement_lease, resume=True, target="review"
        )
        assert isinstance(second_result, dict)
        assert session_status(session_id) == "reviewed"
        assert [q.status for q in question_rows(session_id)] == [
            "reviewed", "reviewed"
        ]
        print("TEST 7 - Remaining review completed after resume: PASSED")

        final_reviews = review_rows(session_id)
        assert len(final_reviews) == 2, final_reviews
        assert final_reviews[0].id == first_reviews[0].id
        assert [r.research_question_id for r in final_reviews] == [
            q.id for q in questions
        ]
        assert [tuple(r) for r in support_rows(session_id)] == [
            (questions[i].id, model.finding_ids[i]) for i in range(2)
        ]
        assert model.calls == Counter({
            "ResearchPlan": 1, "SearchPlan": 2,
            "SourceAnalysis": 2, "ResearchQuestionReview": 2,
        }), model.calls
        print("TEST 8 - Reviews and references not duplicated: PASSED")

        assert search.calls == list(QUERIES), search.calls
        assert retriever.calls == list(URLS), retriever.calls
        assert count_rows("search_attempts", session_id) == 2
        assert count_rows("web_search_results", session_id) == 2
        assert count_rows("sources", session_id) == 2
        assert count_findings(session_id) == 2
        print("TEST 9 - Research not repeated; report not invoked: PASSED")
        print("\nPASS")

    finally:
        if session_id is not None:
            try:
                cleanup_reviews(session_id)
            finally:
                cleanup_graph_test_session(session_id)


if __name__ == "__main__":
    main()
