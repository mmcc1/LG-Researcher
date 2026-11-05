import json
import os
import signal
import subprocess
import sys
import tempfile
import time

from pathlib import Path

from application.research_recovery_service import (
    RecoveryOutcome,
)
from application.research_recovery_worker import (
    ResearchRecoveryWorker,
)


def read_json(path):
    return json.loads(
        path.read_text(encoding="utf-8")
    )


class ControlledRecoveryService:
    def __init__(self):
        self.calls = 0

    def recover(self, limit, cancellation_event=None):
        self.calls += 1

        if self.calls == 1:
            status = "resumed"
        elif self.calls == 2:
            status = "failed"
        else:
            status = "skipped"

        return [
            RecoveryOutcome(
                session_id=f"controlled-{self.calls}",
                status=status,
                error=(
                    "Injected session failure"
                    if status == "failed"
                    else None
                ),
            )
        ]


def child_main(health_file):
    import recovery_worker

    service = ControlledRecoveryService()

    def worker_factory():
        return ResearchRecoveryWorker(
            recovery_service=service
        )

    return recovery_worker.run(
        argv=[
            "--continuous",
            "--interval", "0.2",
            "--limit", "7",
            "--health-file", str(health_file),
        ],
        worker_factory=worker_factory,
    )


def wait_until(predicate, timeout=15):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return True

        time.sleep(0.05)

    return False


def send_shutdown(process):
    if os.name == "nt":
        process.send_signal(
            signal.CTRL_BREAK_EVENT
        )
    else:
        process.send_signal(
            signal.SIGTERM
        )


def main():
    print("RECOVERY WORKER - PROCESS MONITORING")
    print("====================================")

    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)

        health_file = directory / "health.json"
        stdout_file = directory / "stdout.log"
        stderr_file = directory / "stderr.log"

        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--child",
            str(health_file),
        ]

        creationflags = 0
        popen_options = {}

        if os.name == "nt":
            creationflags = (
                subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            popen_options["start_new_session"] = True

        with (
            stdout_file.open("w", encoding="utf-8") as stdout,
            stderr_file.open("w", encoding="utf-8") as stderr,
        ):
            process = subprocess.Popen(
                command,
                stdout=stdout,
                stderr=stderr,
                creationflags=creationflags,
                **popen_options,
            )

            try:
                def has_three_cycles():
                    if not health_file.exists():
                        return False

                    try:
                        state = read_json(health_file)
                    except (
                        OSError,
                        ValueError,
                    ):
                        return False

                    return state.get("cycles", 0) >= 3

                assert wait_until(
                    has_three_cycles
                ), (
                    "Worker did not publish "
                    "three cycles within timeout."
                )

                print(
                    "TEST 1 - Independent worker "
                    "published health: PASSED"
                )

                state = read_json(health_file)

                assert state["resumed"] >= 1
                assert state["failed_sessions"] >= 1
                assert state["skipped"] >= 1
                assert state["cycle_errors"] == 0

                print(
                    "TEST 2 - Mixed recovery outcomes "
                    "recorded: PASSED"
                )

                assert state["last_cycle_at"] is not None
                assert state["last_success_at"] is not None
                assert (
                    state["last_cycle_duration_seconds"]
                    >= 0
                )

                print(
                    "TEST 3 - Cycle timing and timestamps "
                    "recorded: PASSED"
                )

                lock_file = Path(
                    str(health_file) + ".lock"
                )

                assert lock_file.exists()

                print(
                    "TEST 4 - Health-file ownership "
                    "active: PASSED"
                )

                send_shutdown(process)

                process.wait(timeout=10)

                assert process.returncode == 0

                print(
                    "TEST 5 - Graceful process shutdown: PASSED"
                )

            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)

        final_state = read_json(health_file)

        assert final_state["state"] == "stopped"

        print(
            "TEST 6 - Final stopped state "
            "published: PASSED"
        )

        #
        # Test 7 - Ownership released after shutdown
        #

        from application.recovery_health_ownership import (
            RecoveryHealthOwnership,
        )

        ownership = RecoveryHealthOwnership(
            health_file
        )

        try:
            ownership.acquire()

            print(
                "TEST 7 - Health-file ownership "
                "released and reacquired: PASSED"
            )

        finally:
            ownership.release()

        metadata_file = Path(
            str(health_file) + ".lock.info"
        )

        assert not metadata_file.exists()

        output = (
            stdout_file.read_text(encoding="utf-8")
            + "\n"
            + stderr_file.read_text(encoding="utf-8")
        )

        events = []

        for line in output.splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue

            if isinstance(value, dict):
                events.append(value)

        names = [
            event.get("event")
            for event in events
        ]

        assert "worker_started" in names
        assert "recovery_cycle_completed" in names
        assert "worker_stopped" in names

        print(
            "TEST 8 - Structured lifecycle "
            "logs verified: PASSED"
        )

        assert (
            names.count("recovery_cycle_completed")
            == final_state["cycles"]
        )

        print(
            "TEST 9 - Log and health cycle "
            "counts agree: PASSED"
        )

        assert final_state["failed_sessions"] >= 1
        assert final_state["cycle_errors"] == 0
        assert final_state["state"] == "stopped"

        print(
            "TEST 10 - Session failure did not "
            "mark worker unhealthy: PASSED"
        )

    print()
    print("PASS")


if __name__ == "__main__":
    if (
        len(sys.argv) >= 3
        and sys.argv[1] == "--child"
    ):
        sys.exit(
            child_main(
                Path(sys.argv[2])
            )
        )

    main()
