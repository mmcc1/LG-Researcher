import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

from langchain_core.runnables import RunnableLambda
from sqlalchemy import text

from application.research_recovery_service import ResearchRecoveryService
from application.research_workflow_service import ResearchWorkflowService
from persistence.database import SessionLocal
from persistence.research_session_repository import ResearchSessionRepository
from test_research_graph_integration import (
    FakeSearchProvider,
    FakeDocumentRetriever,
    cleanup_graph_test_session,
)
from test_review_graph_integration import cleanup_reviews, rows, status
from test_report_graph_integration import make_graph, cleanup_report
from test_report_graph_pause_resume import report_counts
from test_workflow_controller_integration import (
    ControllerReportModel,
    assert_lease_released,
)
from test_workflow_controller_pause_resume import SessionBindingGraph


class ProcessExitReportModel(ControllerReportModel):
    """Terminate the entire child process inside Report Agent inference."""

    def __init__(self, signal_path):
        super().__init__()
        self.signal_path = Path(signal_path)

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

        def terminate_during_report(messages):
            assert self.session_id is not None

            # All prior graph transitions have committed before this callback.
            with SessionLocal() as db:
                session = ResearchSessionRepository(db).get(self.session_id)
                assert session is not None
                assert session.status == "reporting"
                assert session.execution_owner is not None
                assert session.execution_lease_expires_at is not None
                version = int(session.execution_lease_version)

            payload = {
                "session_id": self.session_id,
                "lease_version": version,
                "worker_pid": os.getpid(),
            }
            temporary_path = self.signal_path.with_suffix(".tmp")
            temporary_path.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(temporary_path, self.signal_path)
            print("Child exiting abruptly during Report Agent inference.", flush=True)

            # This bypasses Python exception handling, finally blocks and
            # normal controller/heartbeat cleanup.
            os._exit(73)

        return RunnableLambda(terminate_during_report)


def build_workflow(model, search, retriever):
    graph = SessionBindingGraph(
        graph=make_graph(model, search, retriever),
        model=model,
    )
    return ResearchWorkflowService(
        graph=graph,
        session_factory=SessionLocal,
        lease_duration_seconds=120,
        heartbeat_interval_seconds=30.0,
    )


def child_main(signal_path):
    model = ProcessExitReportModel(signal_path)
    workflow = build_workflow(
        model,
        FakeSearchProvider(),
        FakeDocumentRetriever(),
    )
    workflow.start(
        topic="Disposable hard-process-termination recovery test",
        scope="Deterministic persisted evidence for process recovery",
    )
    raise AssertionError("Child unexpectedly returned from workflow")


def snapshot(session_id):
    with SessionLocal() as db:
        session = ResearchSessionRepository(db).get(session_id)
        assert session is not None
        return {
            "status": session.status,
            "owner": session.execution_owner,
            "version": int(session.execution_lease_version),
            "expiry": session.execution_lease_expires_at,
            "paused": bool(session.pause_requested),
        }


def expire_test_lease(session_id, owner, version):
    """Expire only the lease belonging to our terminated disposable worker."""
    with SessionLocal() as db:
        result = db.execute(
            text(
                """
                UPDATE dbo.research_sessions
                   SET execution_lease_expires_at =
                       DATEADD(second, -10, SYSUTCDATETIME())
                 WHERE id = :session_id
                   AND execution_owner = :owner
                   AND execution_lease_version = :version
                """
            ),
            {"session_id": session_id, "owner": owner, "version": version},
        )
        assert result.rowcount == 1, "Original worker no longer owns lease"
        db.commit()


def main():
    session_id = None
    process = None
    print("OPERATIONAL RECOVERY - HARD PROCESS TERMINATION")
    print("===============================================")

    with tempfile.TemporaryDirectory(prefix="research_process_kill_") as directory:
        signal_path = Path(directory) / "child_ready.json"
        try:
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", str(signal_path)]
            process = subprocess.Popen(
                command,
                cwd=str(Path(__file__).resolve().parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("TEST 1 - Independent production worker process launched: PASSED")

            deadline = time.monotonic() + 90
            while not signal_path.exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    raise AssertionError(
                        f"Worker exited before report checkpoint: {process.returncode}"
                    )
                time.sleep(0.1)

            assert signal_path.exists(), "Timed out waiting for report checkpoint"
            payload = json.loads(signal_path.read_text(encoding="utf-8"))
            session_id = payload["session_id"]
            print("TEST 2 - Worker reached durable reporting checkpoint: PASSED")

            assert process.wait(timeout=15) == 73, "Worker did not terminate via os._exit"
            print("TEST 3 - Child terminated without Python cleanup: PASSED")

            before = snapshot(session_id)
            assert before["status"] == "reporting"
            assert before["owner"] is not None
            assert before["version"] == payload["lease_version"]
            assert not before["paused"]
            print("TEST 4 - Incomplete session and abandoned lease persisted: PASSED")

            assert report_counts(session_id)["reports"] == 0
            assert len(rows(
                """
                SELECT c.id
                FROM dbo.reviewed_claims c
                JOIN dbo.question_reviews qr ON qr.id = c.question_review_id
                JOIN dbo.research_questions q ON q.id = qr.research_question_id
                WHERE q.research_session_id = :session_id
                """,
                session_id=session_id,
            )) == 1
            print("TEST 5 - Research/review durable; report not yet persisted: PASSED")

            model = ControllerReportModel()
            model.session_id = session_id
            search = FakeSearchProvider()
            retriever = FakeDocumentRetriever()
            workflow = build_workflow(model, search, retriever)
            recovery = ResearchRecoveryService(workflow, SessionLocal)

            assert session_id not in recovery.find_candidates(limit=1000)
            print("TEST 6 - Abandoned but unexpired lease excluded: PASSED")

            expire_test_lease(session_id, before["owner"], before["version"])
            assert session_id in recovery.find_candidates(limit=1000)
            print("TEST 7 - Expired abandoned lease selected: PASSED")

            # Never resume unrelated abandoned sessions from the developer DB.
            recovery.find_candidates = lambda limit=100: [session_id]
            outcomes = recovery.recover()
            assert len(outcomes) == 1
            assert outcomes[0].session_id == session_id
            assert outcomes[0].status == "resumed", outcomes
            print("TEST 8 - Recovery coordinator completed the workflow: PASSED")

            assert status(session_id) == "completed"
            assert report_counts(session_id) == {
                "reports": 1,
                "sections": 1,
                "references": 1,
                "limitations": 1,
            }
            print("TEST 9 - Exactly one complete report hierarchy persisted: PASSED")

            assert len(search.calls) == 0
            assert len(retriever.calls) == 0
            assert model.calls["ResearchReport"] == 1
            assert all(
                count == 0
                for name, count in Counter(model.calls).items()
                if name != "ResearchReport"
            )
            print("TEST 10 - Recovery repeated no research or review operations: PASSED")

            after = snapshot(session_id)
            assert after["version"] == before["version"] + 1
            assert_lease_released(session_id)
            print("TEST 11 - New fencing version and released replacement lease: PASSED")

            fresh_recovery = ResearchRecoveryService(workflow, SessionLocal)
            assert session_id not in fresh_recovery.find_candidates(limit=1000)
            print("TEST 12 - Completed session not rediscovered: PASSED")
            print("\nPASS")

        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=15)

            if session_id is not None:
                try:
                    cleanup_report(session_id)
                finally:
                    try:
                        cleanup_reviews(session_id)
                    finally:
                        cleanup_graph_test_session(session_id)
                print(f"Disposable session removed: {session_id}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        child_main(sys.argv[2])
    elif len(sys.argv) == 1:
        main()
    else:
        raise SystemExit("Usage: python test_operational_recovery_process_kill.py")