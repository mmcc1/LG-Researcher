"""Production LangGraph review-phase integration test (no Ollama/network).

Run: python test_review_graph_integration.py
Requires the existing test helper modules alongside this file.
"""
from collections import Counter
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda
from sqlalchemy import text

from domain.review import ResearchQuestionReview
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
    cleanup_graph_test_session,
)
from test_research_graph_crash_recovery import prepare, state


def rows(sql, **params):
    with SessionLocal() as db:
        return db.execute(text(sql), params).all()


def status(session_id):
    with SessionLocal() as db:
        return ResearchSessionRepository(db).get(session_id).status


def cleanup_reviews(session_id):
    """Remove review descendants before the shared research cleanup."""
    with SessionLocal() as db:
        params = {"session_id": session_id}
        # All review tables are tied to question_reviews through their parent.
        review_ids = """
            SELECT qr.id FROM dbo.question_reviews qr
            JOIN dbo.research_questions q
              ON q.id = qr.research_question_id
            WHERE q.research_session_id = :session_id
        """
        claim_ids = f"""
            SELECT id FROM dbo.reviewed_claims
            WHERE question_review_id IN ({review_ids})
        """
        for sql in (
            f"DELETE FROM dbo.reviewed_claim_support WHERE reviewed_claim_id IN ({claim_ids})",
            f"DELETE FROM dbo.reviewed_claim_contradictions WHERE reviewed_claim_id IN ({claim_ids})",
            f"DELETE FROM dbo.review_contradictions WHERE question_review_id IN ({review_ids})",
            f"DELETE FROM dbo.review_evidence_gaps WHERE question_review_id IN ({review_ids})",
            f"DELETE FROM dbo.reviewed_claims WHERE question_review_id IN ({review_ids})",
            f"DELETE FROM dbo.question_reviews WHERE id IN ({review_ids})",
        ):
            db.execute(text(sql), params)
        db.commit()


class ReviewModel(FakeStructuredChatModel):
    def __init__(self):
        super().__init__()
        self.finding_id = None

    def with_structured_output(self, schema, **kwargs):
        if schema.__name__ != "ResearchQuestionReview":
            return super().with_structured_output(schema, **kwargs)

        def respond(messages):
            self.calls["ResearchQuestionReview"] += 1
            assert self.finding_id is not None
            return ResearchQuestionReview.model_validate({
                "answer": "The controlled evidence establishes the deterministic test marker.",
                "overall_confidence": "high",
                "sufficient_evidence": True,
                "reviewed_claims": [{
                    "claim": "The controlled document contains the deterministic marker.",
                    "confidence": "high",
                    "supporting_finding_ids": [self.finding_id],
                    "contradicting_finding_ids": [],
                }],
                "contradictions": [],
                "evidence_gaps": [],
            })
        return RunnableLambda(respond)


def invoke(graph, session_id, lease, *, resume, target):
    initial = state(session_id, resume)
    initial["execution_target"] = target
    return graph.invoke(
        initial,
        config={
            "configurable": {"execution_lease": lease},
            "recursion_limit": 100,
        },
    )


def main():
    session_id = None
    print("REVIEW GRAPH INTEGRATION")
    print("========================")
    try:
        session_id = create_session()
        print(f"Disposable session: {session_id}")
        set_session_status(session_id, "created")
        lease = acquire_lease(session_id)
        prepare(session_id, lease, resume=False)

        model = ReviewModel()
        search = FakeSearchProvider()
        retriever = FakeDocumentRetriever()
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
        print("TEST 1 - Review test fixture prepared: PASSED")

        invoke(graph, session_id, lease, resume=False, target="research")
        assert status(session_id) == "researched"
        findings = rows("""
            SELECT f.id FROM dbo.findings f
            JOIN dbo.research_questions q ON q.id = f.research_question_id
            WHERE q.research_session_id = :session_id
        """, session_id=session_id)
        assert len(findings) == 1, findings
        model.finding_id = findings[0].id
        print("TEST 2 - Research evidence persisted: PASSED")

        # Use a new execution lease to exercise the production resume route.
        expire_lease(session_id)
        review_lease = acquire_lease(session_id)
        assert review_lease.version != lease.version
        prepare(session_id, review_lease, resume=True)
        print("TEST 3 - Review execution lease prepared: PASSED")

        invoke(graph, session_id, review_lease, resume=True, target="review")
        assert status(session_id) == "reviewed", status(session_id)
        print("TEST 4 - Review graph completed: PASSED")

        assert model.calls["ResearchQuestionReview"] == 1, model.calls
        assert model.calls["ResearchReport"] == 0, model.calls
        print("TEST 5 - Review model invoked once; report not invoked: PASSED")

        review_rows = rows("""
            SELECT qr.id, qr.answer, qr.overall_confidence, qr.sufficient_evidence
            FROM dbo.question_reviews qr
            JOIN dbo.research_questions q ON q.id = qr.research_question_id
            WHERE q.research_session_id = :session_id
        """, session_id=session_id)
        assert len(review_rows) == 1, review_rows
        assert review_rows[0].answer
        print("TEST 6 - Review persisted exactly once: PASSED")

        support_rows = rows("""
            SELECT s.finding_id FROM dbo.reviewed_claim_support s
            JOIN dbo.reviewed_claims c ON c.id = s.reviewed_claim_id
            JOIN dbo.question_reviews qr ON qr.id = c.question_review_id
            JOIN dbo.research_questions q ON q.id = qr.research_question_id
            WHERE q.research_session_id = :session_id
        """, session_id=session_id)
        assert [r.finding_id for r in support_rows] == [model.finding_id], support_rows
        print("TEST 7 - Reviewed claim references persisted finding: PASSED")

        assert len(search.calls) == 1
        assert len(retriever.calls) == 1
        assert model.calls["ResearchPlan"] == 1
        assert model.calls["SearchPlan"] == 1
        assert model.calls["SourceAnalysis"] == 1
        print("TEST 8 - Research not repeated during review: PASSED")
        print("\nPASS")
    finally:
        if session_id is not None:
            try:
                cleanup_reviews(session_id)
            finally:
                cleanup_graph_test_session(session_id)


if __name__ == "__main__":
    main()
