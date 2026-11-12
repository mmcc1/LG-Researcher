import json
import os
import signal
import subprocess
import sys
import tempfile
import time

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def write_json(path, value):

    temporary = path.with_suffix(".tmp")

    temporary.write_text(
        json.dumps(value),
        encoding="utf-8",
    )

    os.replace(temporary, path)


def read_json(path):

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def wait_for_file(path, process, timeout=15):

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:

        if path.exists():
            return read_json(path)

        if process.poll() is not None:
            raise AssertionError(
                f"Child exited early: {process.returncode}"
            )

        time.sleep(0.02)

    raise AssertionError(
        f"Timed out waiting for {path.name}"
    )


def child_main(directory, mode):

    from application.research_recovery_service import (
        RecoveryOutcome,
    )

    from application.research_recovery_worker import (
        ResearchRecoveryWorker,
    )

    from recovery_worker import run

    directory = Path(directory)

    entered_path = directory / "entered.json"
    release_path = directory / "release.json"
    finished_path = directory / "finished.json"
    result_path = directory / "result.json"

    original_handlers = {
        name: signal.getsignal(getattr(signal, name))
        for name in (
            "SIGINT",
            "SIGTERM",
            "SIGBREAK",
        )
        if hasattr(signal, name)
    }

    class ControlledRecoveryService:

        def __init__(self):
            self.calls = 0

        def recover(self, limit=100, cancellation_event=None):

            self.calls += 1

            assert limit == 7

            write_json(
                entered_path,
                {
                    "calls": self.calls,
                    "pid": os.getpid(),
                },
            )

            if mode == "active":

                deadline = time.monotonic() + 20

                while not release_path.exists():

                    if time.monotonic() >= deadline:
                        raise TimeoutError(
                            "Active cycle was never released."
                        )

                    time.sleep(0.02)

            write_json(
                finished_path,
                {"calls": self.calls},
            )

            return [
                RecoveryOutcome(
                    session_id="controlled-session",
                    status="resumed",
                )
            ]

    service = ControlledRecoveryService()

    worker = ResearchRecoveryWorker(
        recovery_service=service,
    )

    exit_code = run(
        argv=[
            "--continuous",
            "--interval",
            "10",
            "--limit",
            "7",
        ],
        worker_factory=lambda: worker,
    )

    handlers_restored = all(
        signal.getsignal(getattr(signal, name))
        == original_handler
        for name, original_handler
        in original_handlers.items()
    )

    write_json(
        result_path,
        {
            "exit_code": exit_code,
            "calls": service.calls,
            "handlers_restored": handlers_restored,
            "finished": finished_path.exists(),
        },
    )

    return exit_code


def launch_child(directory, mode):

    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child",
        str(directory),
        mode,
    ]

    kwargs = {
        "cwd": str(PROJECT_ROOT),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }

    if os.name == "nt":

        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
        )

    else:

        kwargs["start_new_session"] = True

    return subprocess.Popen(
        command,
        **kwargs,
    )


def send_shutdown(process):

    if os.name == "nt":

        process.send_signal(
            signal.CTRL_BREAK_EVENT
        )

    else:

        process.send_signal(
            signal.SIGTERM
        )


def stop_forcefully(process):

    if process.poll() is None:

        process.kill()

        process.communicate(timeout=10)


def wait_for_exit(process, timeout=15):

    try:

        stdout, stderr = process.communicate(
            timeout=timeout
        )

    except subprocess.TimeoutExpired:

        process.kill()

        stdout, stderr = process.communicate(
            timeout=10
        )

        raise AssertionError(
            "Child did not exit after shutdown.\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )

    assert process.returncode == 0, (
        f"Exit code: {process.returncode}\n"
        f"stdout:\n{stdout}\n"
        f"stderr:\n{stderr}"
    )

    return stdout, stderr


def test_idle_shutdown():

    with tempfile.TemporaryDirectory(
        prefix="recovery_idle_shutdown_"
    ) as directory:

        directory = Path(directory)

        process = launch_child(
            directory,
            "idle",
        )

        try:

            entered = wait_for_file(
                directory / "finished.json",
                process,
            )

            assert entered["calls"] == 1

            print(
                "TEST 1 - Independent continuous worker completed first cycle: PASSED"
            )

            started = time.monotonic()

            send_shutdown(process)

            stdout, stderr = wait_for_exit(
                process
            )

            elapsed = time.monotonic() - started

            print("CHILD STDOUT:")
            print(stdout)

            print("CHILD STDERR:")
            print(stderr)

            print(f"Shutdown elapsed: {elapsed:.3f}s")

            assert elapsed < 5, (
                f"Idle shutdown took {elapsed:.2f}s"
            )

            print(
                "TEST 2 - Shutdown interrupts polling wait: PASSED"
            )

            result = read_json(
                directory / "result.json"
            )

            assert result["exit_code"] == 0
            assert result["calls"] == 1

            print(
                "TEST 3 - Idle shutdown prevents another cycle: PASSED"
            )

            assert result["handlers_restored"]

            print(
                "TEST 4 - Original signal handlers restored: PASSED"
            )

        finally:

            stop_forcefully(process)


def test_active_shutdown():

    with tempfile.TemporaryDirectory(
        prefix="recovery_active_shutdown_"
    ) as directory:

        directory = Path(directory)

        process = launch_child(
            directory,
            "active",
        )

        try:

            entered = wait_for_file(
                directory / "entered.json",
                process,
            )

            assert entered["calls"] == 1

            print(
                "TEST 5 - Independent worker entered active cycle: PASSED"
            )

            send_shutdown(process)

            #
            # The recovery service is still blocked.
            # A graceful shutdown must not terminate it.
            #

            time.sleep(0.3)

            assert process.poll() is None

            assert not (
                directory / "finished.json"
            ).exists()

            print(
                "TEST 6 - Shutdown does not interrupt active recovery: PASSED"
            )

            #
            # Allow the active cycle to finish.
            #

            write_json(
                directory / "release.json",
                {"release": True},
            )

            stdout, stderr = wait_for_exit(
                process
            )

            result = read_json(
                directory / "result.json"
            )

            assert result["finished"]
            assert result["exit_code"] == 0

            print(
                "TEST 7 - Active cycle finishes before process exits: PASSED"
            )

            assert result["calls"] == 1

            print(
                "TEST 8 - No subsequent recovery cycle started: PASSED"
            )

            assert result["handlers_restored"]

            print(
                "TEST 9 - Signal handlers restored after active shutdown: PASSED"
            )

        finally:

            #
            # Also unblock the child if an assertion
            # fails before normal release.
            #

            if process.poll() is None:

                write_json(
                    directory / "release.json",
                    {"release": True},
                )

            stop_forcefully(process)


def main():

    print(
        "RECOVERY WORKER - PROCESS SHUTDOWN"
    )

    print(
        "=================================="
    )

    test_idle_shutdown()

    test_active_shutdown()

    print()
    print("PASS")


if __name__ == "__main__":

    if (
        len(sys.argv) == 4
        and sys.argv[1] == "--child"
    ):

        sys.exit(
            child_main(
                sys.argv[2],
                sys.argv[3],
            )
        )

    elif len(sys.argv) == 1:

        main()

    else:

        raise SystemExit(
            "Invalid test arguments."
        )
