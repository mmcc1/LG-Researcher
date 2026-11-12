from collections import Counter
from threading import Event, Thread

from langchain_core.runnables import RunnableLambda

from application.research_workflow_service import ResearchWorkflowService
from persistence.database import SessionLocal
from persistence.execution_lease_repository import ExecutionLeaseUnavailable
from persistence.research_session_repository import ResearchSessionRepository
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


class BlockingControllerReportModel(ControllerReportModel):

    def __init__(
        self,
        report_entered,
        allow_report_to_finish,
    ):

        super().__init__()

        self.report_entered = report_entered
        self.allow_report_to_finish = allow_report_to_finish
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

            self.report_entered.set()

            print(
                "Worker A is waiting during Report Agent inference."
            )

            if not self.allow_report_to_finish.wait(timeout=45):

                raise TimeoutError(
                    "Timed out waiting to release Worker A."
                )

            return runnable.invoke(
                messages
            )

        return RunnableLambda(
            respond_report
        )


def lease_snapshot(
    session_id,
):

    with SessionLocal() as db:

        session = ResearchSessionRepository(db).get(
            session_id
        )

        assert session is not None

        return (
            session.execution_owner,
            session.execution_lease_version,
            session.execution_lease_expires_at,
        )


def main():

    session_id = None
    worker = None

    report_entered = Event()
    allow_report_to_finish = Event()
    worker_finished = Event()

    worker_result = {}
    worker_error = {}

    print("WORKFLOW CONTROLLER EXECUTION-LEASE CONTENTION")
    print("==============================================")

    try:

        model = BlockingControllerReportModel(
            report_entered=report_entered,
            allow_report_to_finish=allow_report_to_finish,
        )

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

        service_a = ResearchWorkflowService(
            graph=graph,
            session_factory=SessionLocal,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )

        service_b = ResearchWorkflowService(
            graph=graph,
            session_factory=SessionLocal,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )

        print("TEST 1 - Two production controllers prepared: PASSED")

        def run_worker_a():

            try:

                worker_result["value"] = service_a.start(
                    topic="Controlled controller lease contention",
                    scope="Deterministic concurrent execution evidence",
                )

            except BaseException as exc:

                worker_error["value"] = exc

            finally:

                worker_finished.set()

        worker = Thread(
            target=run_worker_a,
            name="controller-worker-a",
            daemon=True,
        )

        worker.start()

        assert report_entered.wait(timeout=45), (
            "Worker A did not reach the report inference boundary. "
            f"Worker error: {worker_error.get('value')!r}"
        )

        session_id = model.session_id

        assert session_id is not None
        assert worker.is_alive()
        assert not worker_finished.is_set()

        print("TEST 2 - Worker A blocked during report inference: PASSED")

        assert status(session_id) == "reporting"

        owner_before, version_before, expiry_before = lease_snapshot(
            session_id
        )

        assert owner_before is not None
        assert expiry_before is not None

        print("TEST 3 - Worker A holds active execution lease: PASSED")

        with SessionLocal() as db:

            assert ReportRepository(db).get_for_session(
                session_id
            ) is None

        assert report_counts(session_id) == {
            "reports": 0,
            "sections": 0,
            "references": 0,
            "limitations": 0,
        }

        print("TEST 4 - No report persisted while inference is blocked: PASSED")

        calls_before = Counter(
            model.calls
        )

        search_count_before = len(
            search.calls
        )

        retrieval_count_before = len(
            retriever.calls
        )

        try:

            service_b.resume(
                session_id
            )

        except ExecutionLeaseUnavailable as exc:

            print(
                f"Competing worker rejected: {type(exc).__name__}: {exc}"
            )

        else:

            raise AssertionError(
                "Worker B unexpectedly acquired an active execution lease."
            )

        print("TEST 5 - Worker B rejected at lease acquisition: PASSED")

        assert worker.is_alive()
        assert not worker_finished.is_set()
        assert status(session_id) == "reporting"

        owner_after, version_after, expiry_after = lease_snapshot(
            session_id
        )

        assert owner_after == owner_before
        assert version_after == version_before
        assert expiry_after is not None

        print("TEST 6 - Worker A ownership preserved: PASSED")

        assert Counter(model.calls) == calls_before
        assert len(search.calls) == search_count_before
        assert len(retriever.calls) == retrieval_count_before
        assert model.report_attempts == 1

        print("TEST 7 - Worker B performed no graph or retrieval work: PASSED")

        assert report_counts(session_id) == {
            "reports": 0,
            "sections": 0,
            "references": 0,
            "limitations": 0,
        }

        print("TEST 8 - Contention caused no partial report writes: PASSED")

        allow_report_to_finish.set()

        assert worker_finished.wait(timeout=45), (
            "Worker A did not complete after its inference gate opened."
        )

        worker.join(timeout=5)

        assert not worker.is_alive()

        if "value" in worker_error:

            raise AssertionError(
                "Worker A failed after contention was resolved."
            ) from worker_error["value"]

        result = worker_result["value"]

        assert result.session_id == session_id
        assert status(session_id) == "completed"

        print("TEST 9 - Worker A completed workflow successfully: PASSED")

        assert_lease_released(
            session_id
        )

        print("TEST 10 - Worker A released execution lease: PASSED")

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

        assert report_counts(session_id) == {
            "reports": 1,
            "sections": 1,
            "references": 1,
            "limitations": 1,
        }

        print("TEST 11 - Exactly one valid report hierarchy persisted: PASSED")

        assert model.report_attempts == 1
        assert model.calls["ResearchReport"] == 1
        assert len(search.calls) == search_count_before
        assert len(retriever.calls) == retrieval_count_before

        for name, count in calls_before.items():

            assert model.calls[name] == count + (
                1 if name == "ResearchReport" else 0
            )

        try:

            service_b.resume(
                session_id
            )

        except ValueError as exc:

            assert "already been completed" in str(exc)

        else:

            raise AssertionError(
                "Completed session unexpectedly resumed."
            )

        print("TEST 12 - No duplicate work; completed session protected: PASSED")

        print()
        print("PASS")

    finally:

        allow_report_to_finish.set()

        if worker is not None:

            worker.join(timeout=50)

            if worker.is_alive():

                raise RuntimeError(
                    "Worker A remains active; refusing unsafe fixture cleanup."
                )

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
