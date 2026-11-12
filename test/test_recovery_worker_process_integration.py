import json
import subprocess
import sys
import tempfile
import time

from pathlib import Path

from application.research_recovery_service import (
    ResearchRecoveryService,
)

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from persistence.database import (
    SessionLocal,
)

from test_operational_recovery_natural_expiry import (
    snapshot,
    sql_lease_state,
    wait_for_natural_expiry,
)

from test_review_graph_integration import (
    rows,
    status,
    cleanup_reviews,
)

from test_report_graph_integration import (
    cleanup_report,
)

from test_report_graph_pause_resume import (
    report_counts,
)

from test_research_graph_integration import (
    FakeSearchProvider,
    FakeDocumentRetriever,
    cleanup_graph_test_session,
)

from test_workflow_controller_integration import (
    assert_lease_released,
)


def launch_abrupt_worker(
    signal_path,
):

    project_root = Path(
        __file__
    ).resolve().parent

    return subprocess.Popen(
        [
            sys.executable,
            str(
                project_root
                / "test_operational_recovery_natural_expiry.py"
            ),
            "--worker",
            str(signal_path),
        ],
        cwd=str(project_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_signal(
    process,
    signal_path,
    timeout_seconds=90,
):

    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while time.monotonic() < deadline:

        if signal_path.exists():

            return json.loads(
                signal_path.read_text(
                    encoding="utf-8"
                )
            )

        if process.poll() is not None:

            raise AssertionError(
                "Research worker exited before "
                "the reporting checkpoint: "
                f"{process.returncode}"
            )

        time.sleep(
            0.1
        )

    raise AssertionError(
        "Timed out waiting for research worker "
        "reporting checkpoint."
    )


def launch_recovery_worker(
    session_id,
):

    project_root = Path(
        __file__
    ).resolve().parent

    #
    # The child executes recovery_worker.run()
    # with deterministic production-graph dependencies.
    #
    # This avoids live Ollama inference while retaining:
    #
    # - Actual SQL Server persistence
    # - Actual production LangGraph
    # - Actual workflow controller
    # - Actual execution lease and fencing
    # - Actual recovery coordinator
    # - Actual recovery worker
    # - Actual CLI argument dispatch
    #

    child_code = r'''
import sys

from application.research_recovery_service import (
    ResearchRecoveryService,
)

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from application.research_recovery_worker import (
    ResearchRecoveryWorker,
)

from persistence.database import (
    SessionLocal,
)

from test_research_graph_integration import (
    FakeSearchProvider,
    FakeDocumentRetriever,
)

from test_report_graph_integration import (
    make_graph,
)

from test_workflow_controller_integration import (
    ControllerReportModel,
)

from test_workflow_controller_pause_resume import (
    SessionBindingGraph,
)

from test_review_graph_integration import (
    rows,
)

from recovery_worker import (
    run,
)


session_id = sys.argv[1]

model = ControllerReportModel()

model.session_id = session_id

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

assert len(claim_rows) == 1

model.reviewed_claim_id = claim_rows[0].id

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

workflow = ResearchWorkflowService(
    graph=graph,
    session_factory=SessionLocal,
    lease_duration_seconds=60,
    heartbeat_interval_seconds=5.0,
)

recovery_service = ResearchRecoveryService(
    workflow_service=workflow,
    session_factory=SessionLocal,
)

worker = ResearchRecoveryWorker(
    recovery_service=recovery_service,
)

def worker_factory():

    return worker


exit_code = run(
    argv=[
        "--once",
        "--session-id",
        session_id,
    ],
    worker_factory=worker_factory,
)

assert len(search.calls) == 0
assert len(retriever.calls) == 0

assert model.calls["ResearchReport"] == 1

assert all(
    count == 0
    for name, count in model.calls.items()
    if name != "ResearchReport"
)

sys.exit(exit_code)
'''

    return subprocess.run(
        [
            sys.executable,
            "-c",
            child_code,
            session_id,
        ],
        cwd=str(project_root),
        capture_output=True,
        text=True,
        timeout=120,
    )


def cleanup_session(
    session_id,
):

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


def main():

    print(
        "RECOVERY WORKER - INDEPENDENT PROCESS INTEGRATION"
    )

    print(
        "================================================="
    )

    session_id = None
    original_process = None

    with tempfile.TemporaryDirectory(
        prefix="research_recovery_process_"
    ) as directory:

        signal_path = (
            Path(directory)
            / "child_ready.json"
        )

        try:

            original_process = launch_abrupt_worker(
                signal_path
            )

            print(
                "TEST 1 - Original research worker launched: PASSED"
            )

            payload = wait_for_signal(
                original_process,
                signal_path,
            )

            session_id = payload["session_id"]

            assert (
                original_process.wait(
                    timeout=15
                )
                == 73
            )

            print(
                "TEST 2 - Research worker terminated abruptly: PASSED"
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

            print(
                "TEST 3 - Abandoned lease and reporting state persisted: PASSED"
            )

            assert (
                report_counts(
                    session_id
                )["reports"]
                == 0
            )

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

            assert len(
                claim_rows
            ) == 1

            print(
                "TEST 4 - Research/review durable without report: PASSED"
            )

            expired, _ = sql_lease_state(
                session_id
            )

            assert not expired

            print(
                "TEST 5 - Abandoned lease initially unexpired: PASSED"
            )

            wait_for_natural_expiry(
                session_id
            )

            expired, _ = sql_lease_state(
                session_id
            )

            assert expired

            print(
                "TEST 6 - SQL Server lease expired naturally: PASSED"
            )

            result = launch_recovery_worker(
                session_id
            )

            assert result.returncode == 0, (
                f"Recovery subprocess failed.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )

            assert (
                f"Session {session_id}: resumed"
                in result.stdout
            )

            print(
                "TEST 7 - Independent targeted recovery process succeeded: PASSED"
            )

            assert status(
                session_id
            ) == "completed"

            print(
                "TEST 8 - Durable research session completed: PASSED"
            )

            assert report_counts(
                session_id
            ) == {
                "reports": 1,
                "sections": 1,
                "references": 1,
                "limitations": 1,
            }

            print(
                "TEST 9 - Exactly one complete report hierarchy persisted: PASSED"
            )

            #
            # The child process verifies that
            # research and review are not repeated.
            #
            # The parent verifies persisted state.
            #

            assert len(
                claim_rows
            ) == 1

            print(
                "TEST 10 - Recovery reused durable research/review: PASSED"
            )

            after = snapshot(
                session_id
            )

            assert (
                after["version"]
                == before["version"] + 1
            )

            assert_lease_released(
                session_id
            )

            print(
                "TEST 11 - Fencing advanced and replacement lease released: PASSED"
            )

            print()
            print("PASS")

        finally:

            if (
                original_process is not None
                and original_process.poll() is None
            ):

                original_process.kill()

                original_process.wait(
                    timeout=15
                )

            if session_id is not None:

                cleanup_session(
                    session_id
                )

                print(
                    f"Disposable session removed: {session_id}"
                )


if __name__ == "__main__":

    main()
