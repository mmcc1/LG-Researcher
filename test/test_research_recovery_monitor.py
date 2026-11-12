
import json
import logging
import tempfile
import time

from io import StringIO
from pathlib import Path

from application.research_recovery_monitor import (
    JsonLogFormatter,
    RecoveryHealthMonitor,
)

from application.research_recovery_service import (
    RecoveryOutcome,
)

from application.research_recovery_worker import (
    RecoveryCycleSummary,
)


def make_summary(*statuses):

    outcomes = tuple(
        RecoveryOutcome(
            session_id=f"session-{index}",
            status=status,
        )
        for index, status in enumerate(statuses)
    )

    return RecoveryCycleSummary(
        scanned=len(outcomes),
        resumed=sum(
            status == "resumed"
            for status in statuses
        ),
        paused=sum(
            status == "paused"
            for status in statuses
        ),
        skipped=sum(
            status == "skipped"
            for status in statuses
        ),
        failed=sum(
            status == "failed"
            for status in statuses
        ),
        outcomes=outcomes,
    )


def read_health(path):

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def main():

    print("RESEARCH RECOVERY MONITOR")
    print("=========================")

    with tempfile.TemporaryDirectory() as directory:

        health_path = (
            Path(directory) / "health.json"
        )

        stream = StringIO()

        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonLogFormatter())

        logger = logging.getLogger(
            "test.recovery.monitor"
        )

        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False

        try:

            monitor = RecoveryHealthMonitor(
                health_path,
                logger=logger,
            )

            assert monitor.snapshot["state"] == "starting"

            print(
                "TEST 1 - Initial monitoring state: PASSED"
            )

            monitor.started()

            assert read_health(health_path)["state"] == "running"

            print(
                "TEST 2 - Worker startup health published: PASSED"
            )

            started = monitor.cycle_started()

            assert read_health(health_path)["state"] == "recovering"

            print(
                "TEST 3 - Active recovery state published: PASSED"
            )

            monitor.cycle_completed(
                make_summary(
                    "resumed",
                    "paused",
                    "skipped",
                ),
                started,
            )

            state = read_health(health_path)

            assert state["cycles"] == 1
            assert state["resumed"] == 1
            assert state["paused"] == 1
            assert state["skipped"] == 1
            assert state["failed_sessions"] == 0
            assert state["last_success_at"] is not None
            assert state["last_cycle_duration_seconds"] >= 0

            print(
                "TEST 4 - Successful cycle statistics: PASSED"
            )

            first_success = state["last_success_at"]

            started = monitor.cycle_started()

            monitor.cycle_completed(
                make_summary("failed"),
                started,
            )

            state = read_health(health_path)

            assert state["cycles"] == 2
            assert state["failed_sessions"] == 1
            assert state["last_success_at"] == first_success

            print(
                "TEST 5 - Failed session distinguished from worker failure: PASSED"
            )

            started = monitor.cycle_started()

            monitor.cycle_failed(
                RuntimeError("Injected failure"),
                started,
            )

            state = read_health(health_path)

            assert state["cycle_errors"] == 1
            assert state["cycles"] == 2
            assert "Injected failure" in state["last_error"]

            print(
                "TEST 6 - Coordinator exception recorded: PASSED"
            )

            monitor.stopping()

            assert read_health(health_path)["state"] == "stopping"

            monitor.stopped()

            assert read_health(health_path)["state"] == "stopped"

            print(
                "TEST 7 - Graceful shutdown state published: PASSED"
            )

            records = [
                json.loads(line)
                for line in stream.getvalue().splitlines()
                if line.strip()
            ]

            events = {
                record.get("event")
                for record in records
            }

            assert "worker_started" in events
            assert "recovery_cycle_completed" in events
            assert "recovery_cycle_failed" in events
            assert "worker_stopped" in events

            print(
                "TEST 8 - Structured JSON events emitted: PASSED"
            )

            assert all(
                "timestamp" in record
                and "level" in record
                and "message" in record
                for record in records
            )

            print(
                "TEST 9 - JSON log schema valid: PASSED"
            )

            assert not list(
                Path(directory).glob("*.tmp")
            )

            print(
                "TEST 10 - Atomic writes leave no temporary files: PASSED"
            )

        finally:

            logger.handlers = []
            handler.close()

    print()
    print("PASS")


if __name__ == "__main__":
    main()
