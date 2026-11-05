
import subprocess
import sys

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path

from application.research_recovery_service import (
    RecoveryOutcome,
)

from application.research_recovery_worker import (
    ResearchRecoveryWorker,
)

from recovery_worker import (
    parse_arguments,
    run,
)


class FakeRecoveryService:

    def __init__(
        self,
        status="resumed",
        error=None,
    ):

        self.status = status
        self.error = error

        self.targeted_calls = []
        self.batch_calls = []

    def recover_session(
        self,
        session_id,
    ):

        self.targeted_calls.append(
            session_id
        )

        return RecoveryOutcome(
            session_id=session_id,
            status=self.status,
            error=self.error,
        )

    def recover(
        self,
        limit=100,
    ):

        self.batch_calls.append(
            limit
        )

        return []


def invoke(
    args,
    service,
):

    stdout = StringIO()
    stderr = StringIO()

    def factory():

        return ResearchRecoveryWorker(
            recovery_service=service,
            output=lambda message: None,
        )

    with redirect_stdout(stdout):
        with redirect_stderr(stderr):

            exit_code = run(
                argv=args,
                worker_factory=factory,
            )

    return (
        exit_code,
        stdout.getvalue(),
        stderr.getvalue(),
    )


def main():

    print(
        "RECOVERY WORKER - TARGETED EXECUTION"
    )
    print(
        "===================================="
    )

    session_id = (
        "11111111-1111-4111-8111-111111111111"
    )

    args = parse_arguments(
        ["--once", "--session-id", session_id]
    )

    assert args.session_id == session_id

    print(
        "TEST 1 - Targeted argument accepted: PASSED"
    )

    service = FakeRecoveryService()

    code, stdout, stderr = invoke(
        ["--once", "--session-id", session_id],
        service,
    )

    assert code == 0
    assert service.targeted_calls == [session_id]
    assert service.batch_calls == []

    print(
        "TEST 2 - Targeted recovery avoids batch discovery: PASSED"
    )

    for outcome_status in (
        "resumed",
        "paused",
    ):

        service = FakeRecoveryService(
            status=outcome_status
        )

        code, _, _ = invoke(
            ["--once", "--session-id", session_id],
            service,
        )

        assert code == 0

    print(
        "TEST 3 - Resumed and paused outcomes succeed: PASSED"
    )

    service = FakeRecoveryService(
        status="skipped"
    )

    code, stdout, _ = invoke(
        ["--once", "--session-id", session_id],
        service,
    )

    assert code == 3
    assert "not eligible" in stdout

    print(
        "TEST 4 - Skipped target returns exit code 3: PASSED"
    )

    service = FakeRecoveryService(
        status="failed",
        error="Injected failure",
    )

    code, _, _ = invoke(
        ["--once", "--session-id", session_id],
        service,
    )

    assert code == 1

    print(
        "TEST 5 - Failed target returns exit code 1: PASSED"
    )

    service = FakeRecoveryService()

    code, _, _ = invoke(
        ["--once", "--limit", "7"],
        service,
    )

    assert code == 0
    assert service.batch_calls == [7]
    assert service.targeted_calls == []

    print(
        "TEST 6 - Existing batch mode preserved: PASSED"
    )

    for invalid_args in (
        [
            "--once",
            "--session-id",
            session_id,
            "--limit",
            "5",
        ],
        [
            "--once",
            "--session-id",
            " ",
        ],
    ):

        with redirect_stderr(StringIO()):

            try:

                parse_arguments(
                    invalid_args
                )

            except SystemExit as exc:

                assert exc.code == 2

            else:

                raise AssertionError(
                    "Invalid arguments accepted."
                )

    print(
        "TEST 7 - Conflicting and empty targets rejected: PASSED"
    )

    #
    # Verify a separate Python interpreter can
    # execute the real entry-point run() function.
    #
    # The child injects a fake recovery service,
    # so it cannot recover development sessions.
    #

    child_code = """
import sys

from application.research_recovery_service import RecoveryOutcome
from application.research_recovery_worker import ResearchRecoveryWorker
from recovery_worker import run

class FakeRecoveryService:

    def recover_session(self, session_id):

        return RecoveryOutcome(
            session_id=session_id,
            status="resumed",
        )

    def recover(self, limit=100):

        raise AssertionError(
            "Batch discovery must not run."
        )

def factory():

    return ResearchRecoveryWorker(
        recovery_service=FakeRecoveryService(),
    )

sys.exit(
    run(
        argv=[
            "--once",
            "--session-id",
            sys.argv[1],
        ],
        worker_factory=factory,
    )
)
"""

    project_root = Path(
        __file__
    ).resolve().parent

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            child_code,
            session_id,
        ],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        result.stdout,
        result.stderr,
    )

    assert (
        f"Session {session_id}: resumed"
        in result.stdout
    )

    print(
        "TEST 8 - Independent Python process executes targeted path: PASSED"
    )

    print()
    print("PASS")


if __name__ == "__main__":

    main()
