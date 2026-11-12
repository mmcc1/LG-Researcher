
import json
import os
import subprocess
import sys
import tempfile
import time

from pathlib import Path

from application.recovery_health_ownership import (
    RecoveryHealthOwnership,
    HealthFileAlreadyOwned,
    HealthLockChanged,
    inspect_health_lock,
    clear_stale_health_lock,
)

from application.research_recovery_monitor import (
    RecoveryHealthMonitor,
)

from application.research_recovery_scheduler import (
    ResearchRecoveryScheduler,
)

from application.research_recovery_worker import (
    RecoveryCycleSummary,
)


def wait_until(predicate, timeout=10):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)

    return False


def main():

    print("RECOVERY HEALTH - FAULT TOLERANCE")
    print("=================================")

    with tempfile.TemporaryDirectory() as directory:

        root = Path(directory)
        health_path = root / "health.json"

        # --------------------------------------------------
        # Test 1: Ownership acquisition
        # --------------------------------------------------

        owner = RecoveryHealthOwnership(
            health_path
        )

        owner.acquire()

        info = inspect_health_lock(
            health_path
        )

        assert info is not None
        assert info.pid == os.getpid()
        assert info.token == owner.token

        print(
            "TEST 1 - Exclusive ownership acquired: PASSED"
        )

        # --------------------------------------------------
        # Test 2: Duplicate owner rejected
        # --------------------------------------------------

        duplicate = RecoveryHealthOwnership(
            health_path
        )

        try:
            duplicate.acquire()
        except HealthFileAlreadyOwned:
            pass
        else:
            raise AssertionError(
                "Duplicate ownership was accepted."
            )

        print(
            "TEST 2 - Duplicate ownership rejected: PASSED"
        )

        # --------------------------------------------------
        # Test 3: Clearing requires explicit confirmation
        # --------------------------------------------------

        try:
            clear_stale_health_lock(
                health_path,
                info.token,
            )
        except PermissionError:
            pass
        else:
            raise AssertionError(
                "Unconfirmed lock cleanup was accepted."
            )

        print(
            "TEST 3 - Unconfirmed cleanup rejected: PASSED"
        )

        # --------------------------------------------------
        # Test 4: Wrong ownership token rejected
        # --------------------------------------------------

        try:
            clear_stale_health_lock(
                health_path,
                "incorrect-token",
                owner_confirmed_stopped=True,
            )
        except HealthLockChanged:
            pass
        else:
            raise AssertionError(
                "Incorrect ownership token was accepted."
            )

        print(
            "TEST 4 - Incorrect token rejected: PASSED"
        )

        # --------------------------------------------------
        # Test 5: Normal release
        # --------------------------------------------------

        owner.release()

        assert inspect_health_lock(
            health_path
        ) is None

        print(
            "TEST 5 - Normal ownership release: PASSED"
        )

        # --------------------------------------------------
        # Test 6: Independent process acquires lock
        # --------------------------------------------------

        child_health = root / "child-health.json"
        child_ready = root / "child-ready.json"

        child_code = """
import json
import sys
import time
from pathlib import Path
from application.recovery_health_ownership import (
    RecoveryHealthOwnership,
)

health = Path(sys.argv[1])
ready = Path(sys.argv[2])

with RecoveryHealthOwnership(health) as owner:
    ready.write_text(
        json.dumps({
            "pid": __import__("os").getpid(),
            "token": owner.token,
        }),
        encoding="utf-8",
    )
    time.sleep(60)
"""

        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                child_code,
                str(child_health),
                str(child_ready),
            ],
            cwd=str(
                Path(__file__).resolve().parent
            ),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            assert wait_until(
                lambda: child_ready.exists()
                or process.poll() is not None
            ), "Child process did not start."

            assert process.poll() is None, (
                process.stderr.read()
            )

            child_info = inspect_health_lock(
                child_health
            )

            assert child_info is not None
            assert child_info.pid == process.pid

            print(
                "TEST 6 - Independent process owns lock: PASSED"
            )

            # ----------------------------------------------
            # Test 7: Parent cannot take child's lock
            # ----------------------------------------------

            try:
                RecoveryHealthOwnership(
                    child_health
                ).acquire()
            except HealthFileAlreadyOwned:
                pass
            else:
                raise AssertionError(
                    "Parent acquired active child lock."
                )

            print(
                "TEST 7 - Cross-process duplicate rejected: PASSED"
            )

        finally:
            if process.poll() is None:
                process.kill()

            process.wait(timeout=10)

            if process.stderr is not None:
                process.stderr.close()

        # --------------------------------------------------
        # Test 8: Abrupt exit leaves a stale lock
        # --------------------------------------------------

        stale = inspect_health_lock(
            child_health
        )

        assert stale is not None
        assert stale.token == child_info.token

        print(
            "TEST 8 - Abrupt exit leaves inspectable lock: PASSED"
        )

        # --------------------------------------------------
        # Test 9: Explicit stale-lock recovery
        # --------------------------------------------------

        assert process.poll() is not None

        removed = clear_stale_health_lock(
            child_health,
            expected_token=stale.token,
            owner_confirmed_stopped=True,
        )

        assert removed
        assert inspect_health_lock(
            child_health
        ) is None

        with RecoveryHealthOwnership(
            child_health
        ):
            assert inspect_health_lock(
                child_health
            ) is not None

        print(
            "TEST 9 - Confirmed stale lock recovered: PASSED"
        )

        # --------------------------------------------------
        # Test 10: Health-write failure cannot invalidate
        # successful recovery or prevent future cycles
        # --------------------------------------------------

        fault_health = root / "fault-health.json"

        monitor = RecoveryHealthMonitor(
            fault_health
        )

        monitor.started()

        writes = []

        def failing_write():
            writes.append(True)
            raise OSError(
                "Injected unwritable health destination"
            )

        monitor._write_snapshot = failing_write

        class FakeWorker:

            def __init__(self):
                self.calls = 0
                self.scheduler = None

            def run_once(self, limit):
                self.calls += 1

                if self.calls == 2:
                    self.scheduler.request_stop()

                return RecoveryCycleSummary(
                    scanned=1,
                    resumed=1,
                    paused=0,
                    skipped=0,
                    failed=0,
                    outcomes=(),
                )

        worker = FakeWorker()

        scheduler = ResearchRecoveryScheduler(
            worker=worker,
            interval_seconds=0.1,
            batch_limit=7,
            on_cycle_start=monitor.cycle_started,
            on_cycle=lambda summary: (
                monitor.cycle_completed(
                    summary,
                    time.perf_counter(),
                )
            ),
        )

        worker.scheduler = scheduler

        stats = scheduler.run_forever()

        assert worker.calls == 2
        assert stats.cycles == 2
        assert stats.resumed == 2
        assert stats.failed == 0
        assert stats.cycle_errors == 0
        assert stats.monitor_errors == 4
        assert len(writes) == 4

        print(
            "TEST 10 - Health write failure isolated "
            "from recovery: PASSED"
        )

    print()
    print("PASS")


if __name__ == "__main__":
    main()
