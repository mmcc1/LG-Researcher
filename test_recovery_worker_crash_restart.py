
import json
import os
import signal
import subprocess
import sys
import tempfile
import time

from pathlib import Path

from application.recovery_health_ownership import (
    inspect_health_lock,
    lock_path_for,
)


PROJECT_ROOT = Path(__file__).resolve().parent

STARTUP_TIMEOUT = 20
SHUTDOWN_TIMEOUT = 15
POLL_INTERVAL = 0.05


# ------------------------------------------------------------
# Independent child process
# ------------------------------------------------------------

CHILD_CODE = r"""
import sys

from recovery_worker import run

from application.research_recovery_worker import (
    RecoveryCycleSummary,
)


class FakeRecoveryWorker:

    def __init__(self):
        self.calls = 0

    def run_once(self, limit):
        self.calls += 1

        return RecoveryCycleSummary(
            scanned=1,
            resumed=1,
            paused=0,
            skipped=0,
            failed=0,
            outcomes=(),
        )


if __name__ == "__main__":

    health_file = sys.argv[1]

    exit_code = run(
        argv=[
            "--continuous",
            "--interval",
            "0.2",
            "--limit",
            "7",
            "--health-file",
            health_file,
        ],
        worker_factory=FakeRecoveryWorker,
    )

    sys.exit(exit_code)
"""


# ------------------------------------------------------------
# Process helpers
# ------------------------------------------------------------

def start_worker(health_file, stdout_path, stderr_path):

    stdout_stream = open(
        stdout_path,
        "w",
        encoding="utf-8",
    )

    stderr_stream = open(
        stderr_path,
        "w",
        encoding="utf-8",
    )

    kwargs = {}

    if os.name == "nt":

        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
        )

    else:

        kwargs["start_new_session"] = True

    try:

        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-c",
                CHILD_CODE,
                str(health_file),
            ],
            cwd=str(PROJECT_ROOT),
            stdout=stdout_stream,
            stderr=stderr_stream,
            **kwargs,
        )

    finally:

        # The child retains its own file handles.
        # The parent does not need these streams open.

        stdout_stream.close()
        stderr_stream.close()

    return process


def wait_until(predicate, timeout=STARTUP_TIMEOUT):

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        if predicate():
            return True

        time.sleep(POLL_INTERVAL)

    return False


def read_text(path):

    path = Path(path)

    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def read_health(path):

    try:

        return json.loads(
            Path(path).read_text(
                encoding="utf-8"
            )
        )

    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
    ):

        return None


def health_has_cycles(path, minimum=1):

    health = read_health(path)

    if not isinstance(health, dict):
        return False

    return (
        health.get("cycles", 0) >= minimum
    )


def wait_for_worker_cycles(
    process,
    health_path,
    minimum=1,
):

    return wait_until(
        lambda: (
            process.poll() is not None
            or health_has_cycles(
                health_path,
                minimum,
            )
        )
    )


def terminate_forcefully(process):

    if process.poll() is None:
        process.kill()

    process.wait(
        timeout=SHUTDOWN_TIMEOUT
    )


def request_graceful_shutdown(process):

    if process.poll() is not None:
        return

    if os.name == "nt":

        process.send_signal(
            signal.CTRL_BREAK_EVENT
        )

    else:

        process.send_signal(
            signal.SIGTERM
        )


def cleanup_process(process):

    if process is None:
        return

    if process.poll() is None:

        process.kill()

    try:

        process.wait(
            timeout=SHUTDOWN_TIMEOUT
        )

    except subprocess.TimeoutExpired:

        process.kill()
        process.wait()


def assert_worker_started(
    process,
    health_path,
    stdout_path,
    stderr_path,
):

    ready = wait_for_worker_cycles(
        process,
        health_path,
        minimum=1,
    )

    if (
        not ready
        or process.poll() is not None
        or not health_has_cycles(
            health_path,
            1,
        )
    ):

        raise AssertionError(
            "Worker did not start successfully.\n"
            f"Exit code: {process.poll()}\n"
            f"STDOUT:\n{read_text(stdout_path)}\n"
            f"STDERR:\n{read_text(stderr_path)}"
        )



def wait_for_new_worker(
    process,
    health_path,
    previous_token,
    stdout_path,
    stderr_path,
):

    def replacement_ready():

        if process.poll() is not None:
            return True

        owner = inspect_health_lock(
            health_path
        )

        if owner is None:
            return False

        if owner.pid != process.pid:
            return False

        if owner.token == previous_token:
            return False

        return health_has_cycles(
            health_path,
            minimum=1,
        )

    ready = wait_until(
        replacement_ready,
        timeout=STARTUP_TIMEOUT,
    )

    if (
        not ready
        or process.poll() is not None
    ):

        raise AssertionError(
            "Replacement worker did not start "
            "successfully.\n"
            f"Exit code: {process.poll()}\n"
            f"STDOUT:\n{read_text(stdout_path)}\n"
            f"STDERR:\n{read_text(stderr_path)}"
        )


# ------------------------------------------------------------
# Integration tests
# ------------------------------------------------------------

def main():

    print(
        "RECOVERY WORKER - CRASH AND RESTART"
    )

    print(
        "==================================="
    )

    with tempfile.TemporaryDirectory() as directory:

        root = Path(directory)

        health_path = root / "recovery-health.json"

        worker_a = None
        worker_b = None
        worker_c = None

        try:

            # ------------------------------------------------
            # Test 1: Start production entry point
            # ------------------------------------------------

            a_stdout = root / "worker-a.stdout.log"
            a_stderr = root / "worker-a.stderr.log"

            worker_a = start_worker(
                health_path,
                a_stdout,
                a_stderr,
            )

            assert_worker_started(
                worker_a,
                health_path,
                a_stdout,
                a_stderr,
            )

            print(
                "TEST 1 - Production worker started: PASSED"
            )

            # ------------------------------------------------
            # Test 2: Initial health snapshot
            # ------------------------------------------------

            initial_health = read_health(
                health_path
            )

            assert initial_health is not None
            assert initial_health["cycles"] >= 1
            assert initial_health["resumed"] >= 1

            print(
                "TEST 2 - Initial recovery health published: PASSED"
            )

            # ------------------------------------------------
            # Test 3: Worker A owns health file
            # ------------------------------------------------

            owner_a = inspect_health_lock(
                health_path
            )

            assert owner_a is not None
            assert owner_a.pid == worker_a.pid

            token_a = owner_a.token

            print(
                "TEST 3 - Initial worker owns health file: PASSED"
            )

            # ------------------------------------------------
            # Test 4: Duplicate production worker rejected
            # ------------------------------------------------

            b_stdout = root / "worker-b.stdout.log"
            b_stderr = root / "worker-b.stderr.log"

            worker_b = start_worker(
                health_path,
                b_stdout,
                b_stderr,
            )

            try:

                duplicate_exit = worker_b.wait(
                    timeout=STARTUP_TIMEOUT
                )

            except subprocess.TimeoutExpired:

                raise AssertionError(
                    "Duplicate worker did not exit."
                )

            assert duplicate_exit == 2, (
                "Duplicate worker returned unexpected "
                f"exit code: {duplicate_exit}\n"
                f"{read_text(b_stderr)}"
            )

            assert worker_a.poll() is None

            print(
                "TEST 4 - Duplicate production worker rejected: PASSED"
            )

            # ------------------------------------------------
            # Test 5: Duplicate did not replace ownership
            # ------------------------------------------------

            owner_after_duplicate = inspect_health_lock(
                health_path
            )

            assert owner_after_duplicate is not None

            assert (
                owner_after_duplicate.token
                == token_a
            )

            assert (
                owner_after_duplicate.pid
                == worker_a.pid
            )

            print(
                "TEST 5 - Duplicate did not replace ownership: PASSED"
            )

            # ------------------------------------------------
            # Test 6: Forcefully terminate Worker A
            # ------------------------------------------------

            terminate_forcefully(
                worker_a
            )

            assert worker_a.poll() is not None

            print(
                "TEST 6 - Original worker forcibly terminated: PASSED"
            )

            # ------------------------------------------------
            # Test 7: Lock target survives crash
            # ------------------------------------------------

            assert lock_path_for(
                health_path
            ).exists()

            print(
                "TEST 7 - Persistent OS lock target survived: PASSED"
            )

            # ------------------------------------------------
            # Test 8: Start replacement production worker
            # ------------------------------------------------

            c_stdout = root / "worker-c.stdout.log"
            c_stderr = root / "worker-c.stderr.log"

            worker_c = start_worker(
                health_path,
                c_stdout,
                c_stderr,
            )

            wait_for_new_worker(
                process=worker_c,
                health_path=health_path,
                previous_token=token_a,
                stdout_path=c_stdout,
                stderr_path=c_stderr,
            )

            print(
                "TEST 8 - Replacement worker started: PASSED"
            )

            # ------------------------------------------------
            # Test 9: Ownership transferred to Worker C
            # ------------------------------------------------

            owner_c = inspect_health_lock(
                health_path
            )

            assert owner_c is not None

            print(
                f"Worker C process PID: {worker_c.pid}"
            )

            print(
                f"Ownership metadata PID: {owner_c.pid}"
            )

            print(
                f"Worker C exit status: {worker_c.poll()}"
            )

            assert owner_c.pid == worker_c.pid
            assert owner_c.token != token_a

            print(
                "TEST 9 - Replacement acquired fresh ownership: PASSED"
            )

            # ------------------------------------------------
            # Test 10: Replacement runs multiple cycles
            # ------------------------------------------------

            assert wait_until(
                lambda: (
                    worker_c.poll() is not None
                    or health_has_cycles(
                        health_path,
                        minimum=3,
                    )
                )
            ), "Replacement did not complete three cycles."

            assert worker_c.poll() is None

            replacement_health = read_health(
                health_path
            )

            assert replacement_health is not None
            assert replacement_health["cycles"] >= 3
            assert replacement_health["resumed"] >= 3

            print(
                "TEST 10 - Replacement resumed recovery polling: PASSED"
            )

            # ------------------------------------------------
            # Test 11: Graceful shutdown
            # ------------------------------------------------

            request_graceful_shutdown(
                worker_c
            )

            exit_code = worker_c.wait(
                timeout=SHUTDOWN_TIMEOUT
            )

            assert exit_code == 0, (
                "Replacement shutdown failed.\n"
                f"Exit code: {exit_code}\n"
                f"STDOUT:\n{read_text(c_stdout)}\n"
                f"STDERR:\n{read_text(c_stderr)}"
            )

            print(
                "TEST 11 - Replacement shut down gracefully: PASSED"
            )

            # ------------------------------------------------
            # Test 12: Final stopped health state
            # ------------------------------------------------

            final_health = read_health(
                health_path
            )

            assert final_health is not None

            assert (
                final_health["state"]
                == "stopped"
            )

            print(
                "TEST 12 - Final stopped state published: PASSED"
            )

            # ------------------------------------------------
            # Test 13: OS lock released
            # ------------------------------------------------

            assert inspect_health_lock(
                health_path
            ) is None

            assert lock_path_for(
                health_path
            ).exists()

            print(
                "TEST 13 - Ownership released after shutdown: PASSED"
            )

            # ------------------------------------------------
            # Test 14: Fresh ownership can be acquired
            # ------------------------------------------------

            from application.recovery_health_ownership import (
                RecoveryHealthOwnership,
            )

            with RecoveryHealthOwnership(
                health_path
            ) as final_owner:

                assert final_owner.token is not None

            print(
                "TEST 14 - Subsequent ownership acquisition: PASSED"
            )

        finally:

            # Always clean up every child process,
            # including after failed assertions.

            cleanup_process(worker_a)
            cleanup_process(worker_b)
            cleanup_process(worker_c)

    print()
    print("PASS")


if __name__ == "__main__":
    main()
