
import threading
import time

from types import SimpleNamespace

from application.research_recovery_service import (
    ResearchRecoveryService,
)

from application.research_recovery_worker import (
    ResearchRecoveryWorker,
)

from application.research_recovery_scheduler import (
    ResearchRecoveryScheduler,
)


def check(condition, description):
    if not condition:
        raise AssertionError(description)
    print(f"PASS: {description}")


class FakeRecoveryService(ResearchRecoveryService):

    def __init__(self, candidates):
        self.candidates = candidates
        self.started = []
        self.first_started = threading.Event()
        self.allow_first_to_finish = threading.Event()

    def find_candidates(self, limit=100):
        return self.candidates[:limit]

    def recover_session(self, session_id):
        self.started.append(session_id)

        if len(self.started) == 1:
            self.first_started.set()

            if not self.allow_first_to_finish.wait(5):
                raise TimeoutError(
                    "Test did not release first session."
                )

        return SimpleNamespace(
            session_id=session_id,
            status="resumed",
            error=None,
        )


def test_cancellation_between_sessions():

    service = FakeRecoveryService(
        ["session-1", "session-2", "session-3"]
    )

    worker = ResearchRecoveryWorker(
        recovery_service=service,
        output=lambda message: None,
    )

    scheduler = ResearchRecoveryScheduler(
        worker=worker,
        interval_seconds=30,
        batch_limit=3,
    )

    results = []
    errors = []

    def run_scheduler():
        try:
            results.append(
                scheduler.run_forever()
            )
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(
        target=run_scheduler,
        daemon=True,
    )

    thread.start()

    try:
        check(
            service.first_started.wait(3),
            "First recovery session started",
        )

        scheduler.request_stop()

        check(
            scheduler.stop_requested,
            "Shutdown request recorded",
        )

        check(
            thread.is_alive(),
            "Active session is not forcibly interrupted",
        )

    finally:
        service.allow_first_to_finish.set()
        thread.join(timeout=5)

    check(
        not thread.is_alive(),
        "Scheduler exited after active session",
    )

    check(
        not errors,
        "Scheduler exited without exception",
    )

    check(
        service.started == ["session-1"],
        "No additional recovery sessions started",
    )

    check(
        len(results) == 1 and results[0].cycles == 1,
        "One completed scheduler cycle recorded",
    )

    check(
        results[0].resumed == 1,
        "Completed session counted correctly",
    )


def test_pre_cancelled_batch():

    event = threading.Event()
    event.set()

    service = FakeRecoveryService(
        ["session-1", "session-2"]
    )

    worker = ResearchRecoveryWorker(
        recovery_service=service,
        output=lambda message: None,
    )

    summary = worker.run_once(
        limit=2,
        cancellation_event=event,
    )

    check(
        summary.scanned == 0,
        "Pre-cancelled batch scans no sessions",
    )

    check(
        service.started == [],
        "Pre-cancelled batch starts no workflows",
    )


if __name__ == "__main__":

    test_cancellation_between_sessions()
    test_pre_cancelled_batch()

    print()
    print("COOPERATIVE SHUTDOWN TESTS PASSED")
