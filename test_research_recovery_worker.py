from application.research_recovery_service import (
    RecoveryOutcome,
)

from application.research_recovery_worker import (
    ResearchRecoveryWorker,
)


class FakeRecoveryService:

    def __init__(
        self,
        outcomes=None,
        error=None,
    ):

        self.outcomes = (
            outcomes
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


def main():

    print(
        "RESEARCH RECOVERY WORKER - SINGLE CYCLE"
    )

    print(
        "======================================="
    )

    #
    # -------------------------------------------------
    # Test 1 - Empty recovery cycle
    # -------------------------------------------------
    #

    messages = []

    service = FakeRecoveryService()

    worker = ResearchRecoveryWorker(
        recovery_service=service,
        output=messages.append,
    )

    summary = worker.run_once()

    assert summary.scanned == 0

    assert summary.resumed == 0

    assert summary.paused == 0

    assert summary.skipped == 0

    assert summary.failed == 0

    assert summary.successful

    assert service.calls == [100]

    print(
        "TEST 1 - Empty recovery cycle: PASSED"
    )

    #
    # -------------------------------------------------
    # Test 2 - Mixed recovery outcomes
    # -------------------------------------------------
    #

    outcomes = [
        RecoveryOutcome(
            session_id="session-1",
            status="resumed",
        ),
        RecoveryOutcome(
            session_id="session-2",
            status="paused",
        ),
        RecoveryOutcome(
            session_id="session-3",
            status="skipped",
        ),
        RecoveryOutcome(
            session_id="session-4",
            status="failed",
            error="Injected failure",
        ),
    ]

    messages = []

    service = FakeRecoveryService(
        outcomes=outcomes
    )

    worker = ResearchRecoveryWorker(
        recovery_service=service,
        output=messages.append,
    )

    summary = worker.run_once(
        limit=4
    )

    assert summary.scanned == 4

    assert summary.resumed == 1

    assert summary.paused == 1

    assert summary.skipped == 1

    assert summary.failed == 1

    assert not summary.successful

    assert service.calls == [4]

    assert len(
        summary.outcomes
    ) == 4

    assert any(
        "Injected failure" in message
        for message in messages
    )

    print(
        "TEST 2 - Mixed outcomes counted correctly: PASSED"
    )

    #
    # -------------------------------------------------
    # Test 3 - Custom batch limit
    # -------------------------------------------------
    #

    service = FakeRecoveryService()

    worker = ResearchRecoveryWorker(
        recovery_service=service,
        output=lambda message: None,
    )

    worker.run_once(
        limit=7
    )

    assert service.calls == [7]

    print(
        "TEST 3 - Custom batch limit forwarded: PASSED"
    )

    #
    # -------------------------------------------------
    # Test 4 - Invalid limits rejected
    # -------------------------------------------------
    #

    service = FakeRecoveryService()

    worker = ResearchRecoveryWorker(
        recovery_service=service,
        output=lambda message: None,
    )

    for invalid_limit in (
        0,
        -1,
        1001,
        True,
        1.5,
        "10",
        None,
    ):

        try:

            worker.run_once(
                limit=invalid_limit
            )

        except ValueError:

            pass

        else:

            raise AssertionError(
                "Invalid limit accepted: "
                f"{invalid_limit!r}"
            )

    assert service.calls == []

    print(
        "TEST 4 - Invalid limits rejected: PASSED"
    )

    #
    # -------------------------------------------------
    # Test 5 - Coordinator exception propagates
    # -------------------------------------------------
    #

    service = FakeRecoveryService(
        error=RuntimeError(
            "Injected coordinator failure"
        )
    )

    worker = ResearchRecoveryWorker(
        recovery_service=service,
        output=lambda message: None,
    )

    try:

        worker.run_once()

    except RuntimeError as exc:

        assert (
            str(exc)
            == "Injected coordinator failure"
        )

    else:

        raise AssertionError(
            "Expected coordinator failure"
        )

    print(
        "TEST 5 - Coordinator failure propagates: PASSED"
    )

    #
    # -------------------------------------------------
    # Test 6 - Successful mixed cycle
    # -------------------------------------------------
    #

    service = FakeRecoveryService(
        outcomes=[
            RecoveryOutcome(
                session_id="session-5",
                status="resumed",
            ),
            RecoveryOutcome(
                session_id="session-6",
                status="paused",
            ),
            RecoveryOutcome(
                session_id="session-7",
                status="skipped",
            ),
        ]
    )

    worker = ResearchRecoveryWorker(
        recovery_service=service,
        output=lambda message: None,
    )

    summary = worker.run_once()

    assert summary.scanned == 3

    assert summary.failed == 0

    assert summary.successful

    print(
        "TEST 6 - Non-failing cycle classified as successful: PASSED"
    )

    #
    # -------------------------------------------------
    # Test 7 - Outcome details retained
    # -------------------------------------------------
    #

    expected = RecoveryOutcome(
        session_id="session-8",
        status="failed",
        error="Database unavailable",
    )

    service = FakeRecoveryService(
        outcomes=[
            expected
        ]
    )

    worker = ResearchRecoveryWorker(
        recovery_service=service,
        output=lambda message: None,
    )

    summary = worker.run_once()

    assert summary.outcomes == (
        expected,
    )

    assert summary.failed == 1

    print(
        "TEST 7 - Original recovery outcomes preserved: PASSED"
    )

    print(
        "\nPASS"
    )


if __name__ == "__main__":

    main()
