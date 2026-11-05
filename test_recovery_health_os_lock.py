
"""
Stage 6.1 - OS-backed recovery health ownership tests.

Tests:
    1. OS lock acquisition and metadata
    2. Duplicate ownership rejection
    3. Persistent lock target after normal release
    4. Reacquisition after normal release
    5. Cross-process ownership enforcement
    6. Automatic lock recovery after process termination

Run:
    python test_recovery_health_os_lock.py

No SQL Server or Ollama dependencies are required.
"""

import subprocess
import sys
import tempfile
import time

from pathlib import Path

from application.recovery_health_ownership import (
    RecoveryHealthOwnership,
    HealthFileAlreadyOwned,
    inspect_health_lock,
    lock_path_for,
)


def main():

    print("RECOVERY HEALTH - OS LOCK")
    print("=========================")

    with tempfile.TemporaryDirectory() as directory:

        health = Path(directory) / "health.json"

        # --------------------------------------------------
        # Test 1: Acquisition and metadata
        # --------------------------------------------------

        owner = RecoveryHealthOwnership(health)

        try:

            owner.acquire()

            info = inspect_health_lock(health)

            assert info is not None, (
                "Ownership metadata was not published."
            )

            assert info.token == owner.token, (
                "Ownership token does not match."
            )

            print(
                "TEST 1 - OS lock acquired: PASSED"
            )

            # --------------------------------------------------
            # Test 2: Duplicate rejected
            # --------------------------------------------------

            duplicate = RecoveryHealthOwnership(
                health
            )

            try:

                duplicate.acquire()

            except HealthFileAlreadyOwned:
                pass

            else:

                # Defensive cleanup if duplicate acquisition
                # unexpectedly succeeds.

                duplicate.release()

                raise AssertionError(
                    "Duplicate lock was accepted."
                )

            print(
                "TEST 2 - Duplicate rejected: PASSED"
            )

        finally:

            # Always release the original owner,
            # including when an assertion fails.

            owner.release()

        # --------------------------------------------------
        # Test 3: Normal release retains lock file
        # --------------------------------------------------

        assert lock_path_for(health).exists(), (
            "OS lock target was removed during release."
        )

        print(
            "TEST 3 - Lock target retained: PASSED"
        )

        # --------------------------------------------------
        # Test 4: Reacquisition after normal release
        # --------------------------------------------------

        with RecoveryHealthOwnership(health) as owner:

            info = inspect_health_lock(health)

            assert info is not None, (
                "Metadata missing after reacquisition."
            )

            assert info.token == owner.token, (
                "Reacquired ownership token mismatch."
            )

        print(
            "TEST 4 - Normal reacquisition: PASSED"
        )

        # --------------------------------------------------
        # Test 5: Independent process crash recovery
        # --------------------------------------------------

        ready = Path(directory) / "ready"

        child_code = """
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
        owner.token,
        encoding="utf-8",
    )

    time.sleep(60)
"""

        process = subprocess.Popen(
            [
                sys.executable,
                "-c",
                child_code,
                str(health),
                str(ready),
            ],
            cwd=str(
                Path(__file__).resolve().parent
            ),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:

            deadline = time.monotonic() + 10

            while (
                not ready.exists()
                and process.poll() is None
                and time.monotonic() < deadline
            ):

                time.sleep(0.05)

            if process.poll() is not None:

                stderr = (
                    process.stderr.read()
                    if process.stderr is not None
                    else ""
                )

                raise AssertionError(
                    "Child process exited before "
                    "acquiring ownership.\n"
                    f"{stderr}"
                )

            assert ready.exists(), (
                "Child process did not publish "
                "its readiness marker."
            )

            child_info = inspect_health_lock(
                health
            )

            assert child_info is not None, (
                "Child ownership metadata missing."
            )

            assert child_info.pid == process.pid, (
                "Child ownership PID mismatch."
            )

            assert child_info.token == (
                ready.read_text(
                    encoding="utf-8"
                )
            ), (
                "Child ownership token mismatch."
            )

            duplicate = RecoveryHealthOwnership(
                health
            )

            try:

                duplicate.acquire()

            except HealthFileAlreadyOwned:
                pass

            else:

                duplicate.release()

                raise AssertionError(
                    "Active child lock was acquired "
                    "by the parent process."
                )

            print(
                "TEST 5 - Active child lock protected: PASSED"
            )

        finally:

            # Forcefully terminate the child.
            #
            # This deliberately bypasses the child's
            # normal context-manager cleanup, allowing
            # us to test OS-level lock release.

            if process.poll() is None:
                process.kill()

            process.wait(timeout=10)

            if process.stderr is not None:
                process.stderr.close()

        # --------------------------------------------------
        # Test 6: OS releases lock after process kill
        # --------------------------------------------------

        assert process.poll() is not None, (
            "Child process is still running."
        )

        assert lock_path_for(health).exists(), (
            "Persistent lock target disappeared."
        )

        # No stale-lock deletion or manual cleanup.
        # The new owner must be able to acquire the
        # lock immediately after child termination.

        with RecoveryHealthOwnership(health) as owner:

            info = inspect_health_lock(
                health
            )

            assert info is not None, (
                "Ownership metadata was not refreshed."
            )

            assert info.pid != process.pid, (
                "Metadata still identifies the "
                "terminated child process."
            )

            assert info.token == owner.token, (
                "New ownership token mismatch."
            )

        print(
            "TEST 6 - Lock recovered after process kill: PASSED"
        )

    print()
    print("PASS")


if __name__ == "__main__":
    main()
