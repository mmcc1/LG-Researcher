from collections import Counter

from langchain_core.runnables import RunnableLambda
from sqlalchemy import text

from application.research_workflow_service import ResearchWorkflowService
from persistence.database import SessionLocal
from persistence.report_repository import ReportRepository
from persistence.research_session_repository import ResearchSessionRepository
from test_research_graph_integration import (
    FakeSearchProvider,
    FakeDocumentRetriever,
    cleanup_graph_test_session,
)
from test_review_graph_integration import (
    cleanup_reviews,
    rows,
    status,
)
from test_report_graph_integration import (
    ReportModel,
    make_graph,
    cleanup_report,
)


class ControllerReportModel(ReportModel):

    def __init__(
        self,
    ):

        super().__init__()

        self.session_id = None

    def with_structured_output(
        self,
        schema,
        **kwargs,
    ):

        report_runnable = super().with_structured_output(
            schema,
            **kwargs,
        )

        if schema.__name__ != "ResearchReport":

            return report_runnable

        def respond(
            messages,
        ):

            assert self.session_id is not None

            claim_rows = rows(
                """
                SELECT c.id
                FROM dbo.reviewed_claims c
                JOIN dbo.question_reviews qr
                  ON qr.id = c.question_review_id
                JOIN dbo.research_questions q
                  ON q.id = qr.research_question_id
                WHERE q.research_session_id = :session_id
                """,
                session_id=self.session_id,
            )

            assert len(claim_rows) == 1

            self.reviewed_claim_id = (
                claim_rows[0].id
            )

            return report_runnable.invoke(
                messages
            )

        return RunnableLambda(
            respond
        )


def assert_lease_released(
    session_id,
):

    with SessionLocal() as db:

        session = ResearchSessionRepository(db).get(
            session_id
        )

        assert session is not None

        assert session.execution_owner is None

        assert session.execution_lease_expires_at is None


def main():

    session_id = None

    print("WORKFLOW CONTROLLER INTEGRATION")
    print("===============================")

    try:

        model = ControllerReportModel()

        search = FakeSearchProvider()

        retriever = FakeDocumentRetriever()

        graph = make_graph(
            model,
            search,
            retriever,
        )

        service = ResearchWorkflowService(
            graph=graph,
            session_factory=SessionLocal,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )

        print("TEST 1 - Production controller prepared: PASSED")

        result = service.start_research(
            topic="Controlled workflow controller integration",
            scope="Deterministic test evidence",
        )

        session_id = result.session_id

        model.session_id = session_id

        assert result.topic == "Controlled workflow controller integration"

        assert status(session_id) == "researched"

        print("TEST 2 - Controller started and completed research: PASSED")

        assert_lease_released(
            session_id
        )

        print("TEST 3 - Research execution lease released: PASSED")

        finding_rows = rows(
            """
            SELECT f.id
            FROM dbo.findings f
            JOIN dbo.research_questions q
              ON q.id = f.research_question_id
            WHERE q.research_session_id = :session_id
            """,
            session_id=session_id,
        )

        assert len(finding_rows) == 1

        model.finding_id = (
            finding_rows[0].id
        )

        print("TEST 4 - Research evidence persisted: PASSED")

        original_calls = Counter(
            model.calls
        )

        original_search_count = len(
            search.calls
        )

        original_retrieval_count = len(
            retriever.calls
        )

        resumed = service.resume(
            session_id
        )

        assert resumed.session_id == session_id

        assert status(session_id) == "completed"

        print("TEST 5 - Controller resumed through review and report: PASSED")

        assert_lease_released(
            session_id
        )

        print("TEST 6 - Completed execution lease released: PASSED")

        assert model.calls["ResearchQuestionReview"] == 1

        assert model.calls["ResearchReport"] == 1

        for name, count in original_calls.items():

            assert model.calls[name] == count

        assert len(search.calls) == original_search_count

        assert len(retriever.calls) == original_retrieval_count

        print("TEST 7 - Research not repeated on resume: PASSED")

        with SessionLocal() as db:

            report = ReportRepository(db).get_for_session(
                session_id
            )

        assert report is not None

        assert report.title == "Controlled Research Report"

        assert len(report.sections) == 1

        assert report.sections[0].reviewed_claim_ids == [
            model.reviewed_claim_id
        ]

        print("TEST 8 - Final report retrievable with provenance: PASSED")

        try:

            service.resume(
                session_id
            )

        except ValueError as exc:

            assert "already been completed" in str(exc)

        else:

            raise AssertionError(
                "Completed workflow unexpectedly resumed."
            )

        assert model.calls["ResearchReport"] == 1

        assert_lease_released(
            session_id
        )

        print("TEST 9 - Completed session rejects resume: PASSED")

        print()
        print("PASS")

    finally:

        if session_id is not None:

            try:

                cleanup_report(
                    session_id
                )

            finally:

                try:

                    cleanup_reviews(
                        session_id
                    )

                finally:

                    cleanup_graph_test_session(
                        session_id
                    )

            print(
                f"Disposable session removed: {session_id}"
            )


if __name__ == "__main__":

    main()
