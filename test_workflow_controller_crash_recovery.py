from collections import Counter

from langchain_core.runnables import RunnableLambda

from application.research_workflow_service import ResearchWorkflowService
from persistence.database import SessionLocal
from persistence.report_repository import ReportRepository
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
    make_graph,
    cleanup_report,
)
from test_report_graph_pause_resume import report_counts
from test_workflow_controller_integration import (
    ControllerReportModel,
    assert_lease_released,
)
from test_workflow_controller_pause_resume import SessionBindingGraph


class InjectedControllerReportCrash(RuntimeError):

    pass


class ControllerCrashOnceModel(ControllerReportModel):

    def __init__(
        self,
    ):

        super().__init__()

        self.crash_enabled = True
        self.crash_count = 0
        self.report_attempts = 0

    def with_structured_output(
        self,
        schema,
        **kwargs,
    ):

        runnable = super().with_structured_output(
            schema,
            **kwargs,
        )

        if schema.__name__ == "ResearchQuestionReview":

            def respond_review(
                messages,
            ):

                assert self.session_id is not None

                finding_rows = rows(
                    """
                    SELECT f.id
                    FROM dbo.findings f
                    JOIN dbo.research_questions q
                      ON q.id = f.research_question_id
                    WHERE q.research_session_id = :session_id
                    """,
                    session_id=self.session_id,
                )

                assert len(finding_rows) == 1

                self.finding_id = finding_rows[0].id

                return runnable.invoke(
                    messages
                )

            return RunnableLambda(
                respond_review
            )

        if schema.__name__ != "ResearchReport":

            return runnable

        def respond_report(
            messages,
        ):

            self.report_attempts += 1

            if self.crash_enabled:

                self.crash_enabled = False
                self.crash_count += 1

                print(
                    "Injected exception during controller-managed Report Agent invocation."
                )

                raise InjectedControllerReportCrash(
                    "Simulated controller-managed report worker interruption"
                )

            return runnable.invoke(
                messages
            )

        return RunnableLambda(
            respond_report
        )


def main():

    session_id = None

    print("WORKFLOW CONTROLLER CRASH RECOVERY")
    print("==================================")

    try:

        model = ControllerCrashOnceModel()

        search = FakeSearchProvider()
        retriever = FakeDocumentRetriever()

        graph = SessionBindingGraph(
            graph=make_graph(
                model,
                search,
                retriever,
            ),
            model=model,
        )

        service = ResearchWorkflowService(
            graph=graph,
            session_factory=SessionLocal,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )

        print("TEST 1 - Production controller prepared: PASSED")

        try:

            service.start(
                topic="Controlled controller exception recovery",
                scope="Deterministic durable recovery evidence",
            )

        except InjectedControllerReportCrash as exc:

            assert str(exc) == (
                "Simulated controller-managed report worker interruption"
            )

            print(
                f"Expected controller exception propagated: {exc}"
            )

        else:

            raise AssertionError(
                "Controller unexpectedly swallowed the injected exception."
            )

        session_id = model.session_id

        assert session_id is not None
        assert model.crash_count == 1
        assert model.report_attempts == 1

        print("TEST 2 - Original graph exception propagated: PASSED")

        assert status(session_id) == "reporting"

        print("TEST 3 - Durable reporting state preserved: PASSED")

        assert_lease_released(
            session_id
        )

        print("TEST 4 - Controller released failed execution lease: PASSED")

        with SessionLocal() as db:

            report_before = ReportRepository(db).get_for_session(
                session_id
            )

        assert report_before is None

        assert report_counts(session_id) == {
            "reports": 0,
            "sections": 0,
            "references": 0,
            "limitations": 0,
        }

        print("TEST 5 - Interrupted report left no partial records: PASSED")

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
        assert model.finding_id == finding_rows[0].id

        reviewed_claim_rows = rows(
            """
            SELECT c.id
            FROM dbo.reviewed_claims c
            JOIN dbo.question_reviews qr
              ON qr.id = c.question_review_id
            JOIN dbo.research_questions q
              ON q.id = qr.research_question_id
            WHERE q.research_session_id = :session_id
            """,
            session_id=session_id,
        )

        assert len(reviewed_claim_rows) == 1

        model.reviewed_claim_id = reviewed_claim_rows[0].id

        assert model.calls["ResearchQuestionReview"] == 1
        assert model.calls["ResearchReport"] == 0

        print("TEST 6 - Research and review evidence survived interruption: PASSED")

        original_calls = Counter(
            model.calls
        )

        original_search_count = len(
            search.calls
        )

        original_retrieval_count = len(
            retriever.calls
        )

        resumed_result = service.resume(
            session_id
        )

        assert resumed_result.session_id == session_id
        assert status(session_id) == "completed"

        print("TEST 7 - Replacement controller resumed to completion: PASSED")

        assert_lease_released(
            session_id
        )

        print("TEST 8 - Recovery execution lease released: PASSED")

        with SessionLocal() as db:

            report_after = ReportRepository(db).get_for_session(
                session_id
            )

        assert report_after is not None
        assert report_after.title == "Controlled Research Report"
        assert len(report_after.sections) == 1
        assert report_after.sections[0].reviewed_claim_ids == [
            model.reviewed_claim_id
        ]

        print("TEST 9 - Recovered report provenance valid: PASSED")

        assert report_counts(session_id) == {
            "reports": 1,
            "sections": 1,
            "references": 1,
            "limitations": 1,
        }

        print("TEST 10 - Exactly one complete report persisted: PASSED")

        assert model.report_attempts == 2
        assert model.crash_count == 1
        assert model.calls["ResearchReport"] == 1

        for name, count in original_calls.items():

            if name != "ResearchReport":

                assert model.calls[name] == count

        assert len(search.calls) == original_search_count
        assert len(retriever.calls) == original_retrieval_count

        print("TEST 11 - No duplicate research or review work: PASSED")

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

        print("TEST 12 - Completed workflow rejects further resume: PASSED")

        print()
        print("PASS")

    finally:

        if session_id is None and "model" in locals():

            session_id = model.session_id

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


if __name__ == "__main__":

    main()
