import json
import subprocess
import sys
import tempfile
import threading
import time

from collections import Counter
from pathlib import Path

from sqlalchemy import text

from application.research_recovery_service import (
    ResearchRecoveryService,
)

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from persistence.database import SessionLocal

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from test_operational_recovery_natural_expiry import (
    snapshot,
    wait_for_natural_expiry,
)

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

from test_report_graph_pause_resume import (
    report_counts,
)

from test_workflow_controller_integration import (
    ControllerReportModel,
    assert_lease_released,
)

from test_workflow_controller_pause_resume import (
    SessionBindingGraph,
)


class BlockingGraph:
    """
    Block after the controller has completed its
    fenced eligibility check, but before invoking
    the actual production LangGraph graph.

    The recovery worker remains alive and owns
    its execution lease while blocked.
    """

    def __init__(
        self,
        graph,
    ):

        self.graph = graph

        self.entered = threading.Event()

        self.release = threading.Event()

        self.calls = 0

        self.lock = threading.Lock()

    def invoke(
        self,
        initial_state,
        config=None,
    ):

        with self.lock:

            self.calls += 1

        # At this point the production controller
        # has already acquired the execution lease
        # and completed its fenced eligibility check.

        self.entered.set()

        if not self.release.wait(
            timeout=30
        ):

            raise TimeoutError(
                "Timed out waiting to release "
                "the blocked production graph."
            )

        return self.graph.invoke(
            initial_state,
            config=config,
        )


def build_recovery_workflow(
    model,
    search,
    retriever,
):

    production_graph = SessionBindingGraph(
        graph=make_graph(
            model,
            search,
            retriever,
        ),
        model=model,
    )

    blocking_graph = BlockingGraph(
        production_graph
    )

    workflow = ResearchWorkflowService(
        graph=blocking_graph,
        session_factory=SessionLocal,
        lease_duration_seconds=60,
        heartbeat_interval_seconds=5.0,
    )

    recovery = ResearchRecoveryService(
        workflow_service=workflow,
        session_factory=SessionLocal,
    )

    return (
        blocking_graph,
        workflow,
        recovery,
    )


def request_pause(
    session_id,
):

    with SessionLocal() as db:

        repository = ResearchSessionRepository(
            db
        )

        repository.request_pause(
            session_id
        )


def clear_pause(
    session_id,
):

    with SessionLocal() as db:

        repository = ResearchSessionRepository(
            db
        )

        repository.clear_pause_request(
            session_id
        )


def sql_lease_is_active(
    session_id,
):
    """
    Verify lease validity against SQL Server UTC,
    rather than the local computer's clock.
    """

    with SessionLocal() as db:

        row = db.execute(
            text(
                """
                SELECT
                    CASE
                        WHEN execution_owner IS NOT NULL
                         AND execution_lease_expires_at
                             > SYSUTCDATETIME()
                        THEN 1
                        ELSE 0
                    END AS active

                FROM dbo.research_sessions

                WHERE id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        ).one()

        return bool(
            row.active
        )


def reviewed_claim_count(
    session_id,
):

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
        session_id=session_id,
    )

    return len(
        claim_rows
    )


def main():

    session_id = None

    process = None

    worker = None

    blocking_graph = None

    worker_result = {}

    worker_errors = []

    print(
        "OPERATIONAL RECOVERY - PAUSE DURING EXECUTION"
    )

    print(
        "================================================"
    )

    with tempfile.TemporaryDirectory(
        prefix="research_pause_execution_"
    ) as directory:

        signal_path = (
            Path(directory) / "child_ready.json"
        )

        try:

            #
            # -------------------------------------------------
            # Prepare a genuinely abandoned reporting session
            # -------------------------------------------------
            #

            # Reuse the child process from the successful
            # natural-expiry integration test.
            #
            # It runs the real research and review phases,
            # reaches report inference, persists its
            # checkpoint, and terminates using os._exit(73).

            existing_test = (
                Path(__file__).resolve().parent
                / "test_operational_recovery_natural_expiry.py"
            )

            assert existing_test.is_file(), (
                "Natural-expiry test file not found: "
                f"{existing_test}"
            )

            command = [
                sys.executable,
                str(existing_test),
                "--worker",
                str(signal_path),
            ]

            process = subprocess.Popen(
                command,
                cwd=str(
                    Path(__file__).resolve().parent
                ),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            print(
                "TEST 1 - Independent production worker launched: PASSED"
            )

            deadline = (
                time.monotonic() + 90
            )

            while (
                not signal_path.exists()
                and time.monotonic() < deadline
            ):

                if process.poll() is not None:

                    raise AssertionError(
                        "Child exited before reaching "
                        "the reporting checkpoint. "
                        f"Exit code: {process.returncode}"
                    )

                time.sleep(
                    0.1
                )

            assert signal_path.exists(), (
                "Timed out waiting for child "
                "reporting checkpoint."
            )

            payload = json.loads(
                signal_path.read_text(
                    encoding="utf-8"
                )
            )

            session_id = payload[
                "session_id"
            ]

            assert process.wait(
                timeout=15
            ) == 73

            print(
                "TEST 2 - Child terminated abruptly during reporting: PASSED"
            )

            before = snapshot(
                session_id
            )

            assert before["status"] == "reporting"

            assert before["owner"] is not None

            assert not before["paused"]

            assert (
                before["version"]
                == payload["lease_version"]
            )

            assert (
                report_counts(
                    session_id
                )["reports"]
                == 0
            )

            assert reviewed_claim_count(
                session_id
            ) == 1

            print(
                "TEST 3 - Durable research/review persisted without report: PASSED"
            )

            #
            # -------------------------------------------------
            # Allow abandoned execution lease to expire
            # -------------------------------------------------
            #

            wait_for_natural_expiry(
                session_id,
                timeout_seconds=20,
            )

            expired_state = snapshot(
                session_id
            )

            assert (
                expired_state["owner"]
                == before["owner"]
            )

            assert (
                expired_state["version"]
                == before["version"]
            )

            print(
                "TEST 4 - Abandoned execution lease expired naturally: PASSED"
            )

            #
            # -------------------------------------------------
            # Prepare recovery with a blocking graph wrapper
            # -------------------------------------------------
            #

            model = ControllerReportModel()

            model.session_id = session_id

            search = FakeSearchProvider()

            retriever = FakeDocumentRetriever()

            (
                blocking_graph,
                workflow,
                recovery,
            ) = build_recovery_workflow(
                model,
                search,
                retriever,
            )

            assert session_id in recovery.find_candidates(
                limit=1000
            )

            # Restrict coordinator execution to the
            # disposable session, never unrelated
            # abandoned sessions in the database.

            recovery.find_candidates = (
                lambda limit=100: [session_id]
            )

            print(
                "TEST 5 - Disposable session eligible for automatic recovery: PASSED"
            )

            #
            # -------------------------------------------------
            # Start automatic recovery on a background thread
            # -------------------------------------------------
            #

            def recover_worker():

                try:

                    worker_result["outcomes"] = (
                        recovery.recover()
                    )

                except BaseException as exc:

                    worker_errors.append(
                        exc
                    )

            worker = threading.Thread(
                target=recover_worker,
                name="pause-during-recovery-worker",
                daemon=True,
            )

            worker.start()

            assert blocking_graph.entered.wait(
                timeout=20
            ), (
                "Recovery did not reach the "
                "production graph boundary."
            )

            assert worker.is_alive()

            assert blocking_graph.calls == 1

            print(
                "TEST 6 - Recovery passed eligibility and reached graph boundary: PASSED"
            )

            #
            # -------------------------------------------------
            # Verify recovery lease is currently owned
            # -------------------------------------------------
            #

            during = snapshot(
                session_id
            )

            assert during["owner"] is not None

            assert (
                during["owner"]
                != before["owner"]
            )

            assert (
                during["version"]
                == before["version"] + 1
            )

            assert sql_lease_is_active(
                session_id
            )

            print(
                "TEST 7 - Replacement execution lease active during recovery: PASSED"
            )

            #
            # -------------------------------------------------
            # Inject pause after eligibility approval
            # -------------------------------------------------
            #

            # This occurs AFTER the controller has
            # acquired its lease and approved recovery,
            # but BEFORE the production graph has
            # executed its first node.

            request_pause(
                session_id
            )

            paused_state = snapshot(
                session_id
            )

            assert paused_state["paused"]

            assert paused_state["owner"] is not None

            assert sql_lease_is_active(
                session_id
            )

            print(
                "TEST 8 - Pause committed while recovery lease remained active: PASSED"
            )

            #
            # -------------------------------------------------
            # Release production graph
            # -------------------------------------------------
            #

            blocking_graph.release.set()

            worker.join(
                timeout=30
            )

            assert not worker.is_alive(), (
                "Recovery worker did not terminate."
            )

            assert not worker_errors, (
                worker_errors
            )

            outcomes = worker_result[
                "outcomes"
            ]

            assert len(outcomes) == 1

            assert (
                outcomes[0].session_id
                == session_id
            )

            assert outcomes[0].status == "paused", (
                outcomes
            )

            print(
                "TEST 9 - Production graph honoured pause at reporting entry: PASSED"
            )

            #
            # -------------------------------------------------
            # Validate durable state after pause
            # -------------------------------------------------
            #

            assert status(
                session_id
            ) == "reporting"

            assert snapshot(
                session_id
            )["paused"]

            assert report_counts(
                session_id
            ) == {
                "reports": 0,
                "sections": 0,
                "references": 0,
                "limitations": 0,
            }

            print(
                "TEST 10 - Reporting state preserved without generating a report: PASSED"
            )

            assert (
                model.calls["ResearchReport"]
                == 0
            )

            assert len(
                search.calls
            ) == 0

            assert len(
                retriever.calls
            ) == 0

            assert reviewed_claim_count(
                session_id
            ) == 1

            print(
                "TEST 11 - Pause prevented report inference and repeated research: PASSED"
            )

            assert_lease_released(
                session_id
            )

            print(
                "TEST 12 - Paused recovery released its execution lease: PASSED"
            )

            #
            # -------------------------------------------------
            # Explicit resume after clearing pause
            # -------------------------------------------------
            #

            clear_pause(
                session_id
            )

            assert not snapshot(
                session_id
            )["paused"]

            # The blocking wrapper is no longer needed.
            # Build a fresh controller using the same
            # production graph and deterministic model.

            resume_model = ControllerReportModel()

            resume_model.session_id = session_id

            resume_search = FakeSearchProvider()

            resume_retriever = FakeDocumentRetriever()

            resume_graph = SessionBindingGraph(
                graph=make_graph(
                    resume_model,
                    resume_search,
                    resume_retriever,
                ),
                model=resume_model,
            )

            resume_workflow = ResearchWorkflowService(
                graph=resume_graph,
                session_factory=SessionLocal,
                lease_duration_seconds=60,
                heartbeat_interval_seconds=5.0,
            )

            result = resume_workflow.resume(
                session_id
            )

            assert result.session_id == session_id

            assert status(
                session_id
            ) == "completed"

            print(
                "TEST 13 - Explicit resume completed reporting after pause cleared: PASSED"
            )

            #
            # -------------------------------------------------
            # Verify exactly-once report persistence
            # -------------------------------------------------
            #

            assert report_counts(
                session_id
            ) == {
                "reports": 1,
                "sections": 1,
                "references": 1,
                "limitations": 1,
            }

            assert (
                resume_model.calls["ResearchReport"]
                == 1
            )

            assert len(
                resume_search.calls
            ) == 0

            assert len(
                resume_retriever.calls
            ) == 0

            assert all(
                count == 0
                for name, count in Counter(
                    resume_model.calls
                ).items()
                if name != "ResearchReport"
            )

            print(
                "TEST 14 - Exactly one report persisted without repeated research/review: PASSED"
            )

            #
            # -------------------------------------------------
            # Verify final fencing and recovery eligibility
            # -------------------------------------------------
            #

            after = snapshot(
                session_id
            )

            # Original worker: version N
            # Recovery worker: version N + 1
            # Explicit resume: version N + 2

            assert (
                after["version"]
                == before["version"] + 2
            )

            assert_lease_released(
                session_id
            )

            fresh_recovery = ResearchRecoveryService(
                workflow_service=resume_workflow,
                session_factory=SessionLocal,
            )

            assert session_id not in fresh_recovery.find_candidates(
                limit=1000
            )

            print(
                "TEST 15 - Fencing advanced and completed session excluded: PASSED"
            )

            print(
                "\nPASS"
            )

        finally:

            #
            # -------------------------------------------------
            # Always release blocked worker
            # -------------------------------------------------
            #

            if blocking_graph is not None:

                blocking_graph.release.set()

            if worker is not None:

                worker.join(
                    timeout=35
                )

                if worker.is_alive():

                    raise RuntimeError(
                        "Recovery worker is still active; "
                        "refusing to clean up its session."
                    )

            #
            # -------------------------------------------------
            # Terminate child if still alive
            # -------------------------------------------------
            #

            if (
                process is not None
                and process.poll() is None
            ):

                process.kill()

                process.wait(
                    timeout=15
                )

            #
            # -------------------------------------------------
            # Remove disposable database records
            # -------------------------------------------------
            #

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
                    "Disposable session removed: "
                    f"{session_id}"
                )


if __name__ == "__main__":

    main()
