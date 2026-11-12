from collections import Counter
from threading import Event, Thread, current_thread
from unittest.mock import patch

from langchain_core.runnables import RunnableLambda

import application.research_workflow_service as workflow_module
from application.research_workflow_service import ResearchWorkflowService
from persistence.database import SessionLocal
from persistence.report_repository import ReportRepository
from test_search_result_fencing import expire_lease
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
from test_workflow_controller_lease_contention import lease_snapshot


class BlockedReportModel(ControllerReportModel):

    def __init__(self, report_entered, release_stale_worker):

        super().__init__()

        self.report_entered = report_entered
        self.release_stale_worker = release_stale_worker
        self.report_attempts = 0

    def with_structured_output(self, schema, **kwargs):

        runnable = super().with_structured_output(schema, **kwargs)

        if schema.__name__ == "ResearchQuestionReview":

            def respond_review(messages):

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

                return runnable.invoke(messages)

            return RunnableLambda(respond_review)

        if schema.__name__ != "ResearchReport":

            return runnable

        def respond_report(messages):

            self.report_attempts += 1

            if current_thread().name == "takeover-worker-a":

                self.report_entered.set()

                print("Worker A blocked during Report Agent inference.")

                if not self.release_stale_worker.wait(timeout=45):

                    raise TimeoutError("Worker A was not released in time.")

            return runnable.invoke(messages)

        return RunnableLambda(respond_report)


class DisabledHeartbeat:
    """Suppress renewal for Worker A only; all other workers use the real heartbeat."""

    def __init__(self, *args, **kwargs):

        pass

    def start(self):

        pass

    def stop(self):

        pass


def main():

    session_id = None
    worker = None
    report_entered = Event()
    release_stale_worker = Event()
    worker_finished = Event()
    worker_error = {}
    worker_result = {}

    print("WORKFLOW CONTROLLER LEASE EXPIRY / TAKEOVER")
    print("===========================================")

    try:

        model = BlockedReportModel(
            report_entered=report_entered,
            release_stale_worker=release_stale_worker,
        )

        search = FakeSearchProvider()
        retriever = FakeDocumentRetriever()

        graph = SessionBindingGraph(
            graph=make_graph(model, search, retriever),
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

        real_heartbeat = workflow_module.ExecutionLeaseHeartbeat

        def heartbeat_factory(*args, **kwargs):

            if current_thread().name == "takeover-worker-a":

                return DisabledHeartbeat(*args, **kwargs)

            return real_heartbeat(*args, **kwargs)

        def run_worker_a():

            try:

                worker_result["value"] = service_a.start(
                    topic="Controlled controller expired-lease takeover",
                    scope="Deterministic lease takeover evidence",
                )

            except BaseException as exc:

                worker_error["value"] = exc

            finally:

                worker_finished.set()

        # Worker A has no heartbeat, so its lease cannot be renewed after
        # the test deliberately expires it. Worker B uses the real heartbeat.
        with patch.object(
            workflow_module,
            "ExecutionLeaseHeartbeat",
            side_effect=heartbeat_factory,
        ):

            worker = Thread(
                target=run_worker_a,
                name="takeover-worker-a",
                daemon=True,
            )

            worker.start()

            assert report_entered.wait(timeout=45), (
                f"Worker A failed before report inference: {worker_error!r}"
            )

            session_id = model.session_id

            assert session_id is not None
            assert worker.is_alive()
            assert status(session_id) == "reporting"

            print("TEST 2 - Worker A blocked during reporting: PASSED")

            owner_a, version_a, expiry_a = lease_snapshot(session_id)

            assert owner_a is not None
            assert expiry_a is not None

            print("TEST 3 - Worker A holds an execution lease: PASSED")

            assert report_counts(session_id) == {
                "reports": 0,
                "sections": 0,
                "references": 0,
                "limitations": 0,
            }

            print("TEST 4 - No report persisted before takeover: PASSED")

            calls_before = Counter(model.calls)
            search_count = len(search.calls)
            retrieval_count = len(retriever.calls)

            expire_lease(session_id)

            owner_expired, version_expired, _ = lease_snapshot(session_id)

            assert owner_expired == owner_a
            assert version_expired == version_a
            assert worker.is_alive()

            print("TEST 5 - Worker A lease deliberately expired: PASSED")

            result_b = service_b.resume(session_id)

            assert result_b.session_id == session_id
            assert status(session_id) == "completed"

            print("TEST 6 - Worker B took over and completed: PASSED")

            assert worker.is_alive()
            assert not worker_finished.is_set()
            assert model.report_attempts == 2

            print("TEST 7 - Worker A remained blocked during takeover: PASSED")

            with SessionLocal() as db:

                report = ReportRepository(db).get_for_session(session_id)

            assert report is not None
            assert report.title == "Controlled Research Report"
            assert len(report.sections) == 1
            assert report.sections[0].reviewed_claim_ids == [
                model.reviewed_claim_id
            ]

            print("TEST 8 - Replacement report provenance valid: PASSED")

            assert report_counts(session_id) == {
                "reports": 1,
                "sections": 1,
                "references": 1,
                "limitations": 1,
            }

            print("TEST 9 - Exactly one complete report persisted: PASSED")

            assert_lease_released(session_id)

            print("TEST 10 - Worker B released its execution lease: PASSED")

            release_stale_worker.set()

            assert worker_finished.wait(timeout=45)
            worker.join(timeout=5)
            assert not worker.is_alive()

            assert "value" not in worker_result
            assert "value" in worker_error
            assert type(worker_error["value"]).__name__ == (
                "ExecutionLeaseFenceRejected"
            ), repr(worker_error["value"])

            print(
                "Stale Worker A rejected:",
                type(worker_error["value"]).__name__,
            )

            print("TEST 11 - Stale Worker A fenced at persistence: PASSED")

            assert_lease_released(session_id)
            assert status(session_id) == "completed"

            assert report_counts(session_id) == {
                "reports": 1,
                "sections": 1,
                "references": 1,
                "limitations": 1,
            }

            assert model.report_attempts == 2
            assert model.calls["ResearchReport"] == 2
            assert len(search.calls) == search_count
            assert len(retriever.calls) == retrieval_count

            for name, count in calls_before.items():

                if name != "ResearchReport":

                    assert model.calls[name] == count

            print("TEST 12 - No duplicate work or stale cleanup damage: PASSED")

            print()
            print("PASS")

    finally:

        release_stale_worker.set()

        if worker is not None:

            worker.join(timeout=50)

            if worker.is_alive():

                raise RuntimeError(
                    "Worker A is still running; refusing unsafe fixture cleanup."
                )

        if session_id is None and "model" in locals():

            session_id = model.session_id

        if session_id is not None:

            try:

                cleanup_report(session_id)

            finally:

                try:

                    cleanup_reviews(session_id)

                finally:

                    cleanup_graph_test_session(session_id)


if __name__ == "__main__":

    main()
