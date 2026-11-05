
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO

from recovery_worker import (
    parse_arguments,
    run,
)

from application.research_recovery_service import (
    RecoveryOutcome,
)

from application.research_recovery_worker import (
    RecoveryCycleSummary,
    ResearchRecoveryWorker,
)


class FakeRecoveryService:

    def __init__(
        self,
        outcomes=None,
        error=None,
    ):

        self.outcomes = (
            list(outcomes)
            if outcomes is not None
            else []
        )

        self.error = error

        self.calls = []

    def recover(
        self,
        limit=100,
        cancellation_event=None,
    ):

        self.calls.append(
            limit
        )

        if self.error is not None:

            raise self.error

        return list(
            self.outcomes
        )


def make_worker_factory(
    service,
):

    def factory():

        return ResearchRecoveryWorker(
            recovery_service=service,
            output=lambda message: None,
        )

    return factory


def invoke(
    argv,
    service,
):

    stdout = StringIO()
    stderr = StringIO()

    with redirect_stdout(stdout):
        with redirect_stderr(stderr):

            exit_code = run(
                argv=argv,
                worker_factory=make_worker_factory(
                    service
                ),
            )

    return (
        exit_code,
        stdout.getvalue(),
        stderr.getvalue(),
    )


def expect_argument_error(
    argv,
):

    stderr = StringIO()

    with redirect_stderr(stderr):

        try:

            parse_arguments(
                argv
            )

        except SystemExit as exc:

            assert exc.code == 2

        else:

            raise AssertionError(
                f"Expected argument error: {argv}"
            )


def main():

    print(
        "RECOVERY WORKER - PRODUCTION ENTRY POINT"
    )

    print(
        "========================================"
    )

    #
    # Test 1 - Default batch limit
    #

    args = parse_arguments(
        ["--once"]
    )

    assert args.once is True
    assert args.limit == 25

    print(
        "TEST 1 - Default batch limit: PASSED"
    )

    #
    # Test 2 - Custom batch limit
    #

    args = parse_arguments(
        ["--once", "--limit", "7"]
    )

    assert args.limit == 7

    print(
        "TEST 2 - Custom batch limit: PASSED"
    )

    #
    # Test 3 - Required execution mode
    #

    expect_argument_error(
        []
    )

    print(
        "TEST 3 - Explicit single-cycle mode required: PASSED"
    )

    #
    # Test 4 - Invalid batch limits
    #

    for value in (
        "0",
        "-1",
        "1001",
        "1.5",
        "abc",
    ):

        expect_argument_error(
            ["--once", "--limit", value]
        )

    print(
        "TEST 4 - Invalid batch limits rejected: PASSED"
    )

    #
    # Test 5 - Successful empty cycle
    #

    service = FakeRecoveryService()

    exit_code, stdout, stderr = invoke(
        ["--once"],
        service,
    )

    assert exit_code == 0
    assert service.calls == [25]
    assert "successfully" in stdout
    assert stderr == ""

    print(
        "TEST 5 - Empty cycle exits successfully: PASSED"
    )

    #
    # Test 6 - Successful recovered session
    #

    service = FakeRecoveryService(
        outcomes=[
            RecoveryOutcome(
                session_id="session-1",
                status="resumed",
            ),
        ]
    )

    exit_code, stdout, stderr = invoke(
        ["--once", "--limit", "3"],
        service,
    )

    assert exit_code == 0
    assert service.calls == [3]
    assert stderr == ""

    print(
        "TEST 6 - Recovered session exits successfully: PASSED"
    )

    #
    # Test 7 - Paused and skipped are not failures
    #

    service = FakeRecoveryService(
        outcomes=[
            RecoveryOutcome(
                session_id="session-2",
                status="paused",
            ),
            RecoveryOutcome(
                session_id="session-3",
                status="skipped",
            ),
        ]
    )

    exit_code, stdout, stderr = invoke(
        ["--once"],
        service,
    )

    assert exit_code == 0
    assert service.calls == [25]

    print(
        "TEST 7 - Paused and skipped outcomes accepted: PASSED"
    )

    #
    # Test 8 - Session recovery failure
    #

    service = FakeRecoveryService(
        outcomes=[
            RecoveryOutcome(
                session_id="session-4",
                status="failed",
                error="Injected recovery failure",
            ),
        ]
    )

    exit_code, stdout, stderr = invoke(
        ["--once"],
        service,
    )

    assert exit_code == 1
    assert "session failures" in stdout

    print(
        "TEST 8 - Session failure returns exit code 1: PASSED"
    )

    #
    # Test 9 - Coordinator failure
    #

    service = FakeRecoveryService(
        error=RuntimeError(
            "Injected coordinator failure"
        )
    )

    exit_code, stdout, stderr = invoke(
        ["--once"],
        service,
    )

    assert exit_code == 2
    assert "RuntimeError" in stderr
    assert "Injected coordinator failure" in stderr

    print(
        "TEST 9 - Coordinator failure returns exit code 2: PASSED"
    )

    #
    # Test 10 - Worker initialization failure
    #

    def failing_factory():

        raise RuntimeError(
            "Injected initialization failure"
        )

    stdout = StringIO()
    stderr = StringIO()

    with redirect_stdout(stdout):
        with redirect_stderr(stderr):

            exit_code = run(
                argv=["--once"],
                worker_factory=failing_factory,
            )

    assert exit_code == 2
    assert "Injected initialization failure" in stderr.getvalue()

    print(
        "TEST 10 - Initialization failure returns exit code 2: PASSED"
    )

    #
    # Test 11 - Maximum permitted batch limit
    #

    service = FakeRecoveryService()

    exit_code, stdout, stderr = invoke(
        ["--once", "--limit", "1000"],
        service,
    )

    assert exit_code == 0
    assert service.calls == [1000]

    print(
        "TEST 11 - Maximum batch limit forwarded: PASSED"
    )

    #
    # Test 12 - Recovery outcomes retained
    #

    outcomes = [
        RecoveryOutcome(
            session_id="session-5",
            status="resumed",
        ),
        RecoveryOutcome(
            session_id="session-6",
            status="skipped",
        ),
    ]

    service = FakeRecoveryService(
        outcomes=outcomes
    )

    worker = ResearchRecoveryWorker(
        recovery_service=service,
        output=lambda message: None,
    )

    summary = worker.run_once(
        limit=2
    )

    assert isinstance(
        summary,
        RecoveryCycleSummary,
    )

    assert summary.outcomes == tuple(
        outcomes
    )

    assert summary.scanned == 2
    assert summary.successful

    print(
        "TEST 12 - Structured recovery results retained: PASSED"
    )

    print()
    print("PASS")


if __name__ == "__main__":

    main()
