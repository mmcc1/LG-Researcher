
import math
import threading
import time

from application.research_recovery_service import (
    RecoveryOutcome,
)

from application.research_recovery_worker import (
    ResearchRecoveryWorker,
)

from application.research_recovery_scheduler import (
    ResearchRecoveryScheduler,
)


class FakeRecoveryService:

    def __init__(self):

        self.calls = 0
        self.lock = threading.Lock()

    def recover(
        self,
        limit=100,
        cancellation_event=None,
    ):

        with self.lock:

            self.calls += 1

        return [
            RecoveryOutcome(
                session_id="test-session",
                status="resumed",
            )
        ]


def make_scheduler(
    service=None,
    interval=0.1,
    limit=5,
    on_cycle=None,
):

    if service is None:

        service = FakeRecoveryService()

    worker = ResearchRecoveryWorker(
        recovery_service=service,
        output=lambda message: None,
    )

    return ResearchRecoveryScheduler(
        worker=worker,
        interval_seconds=interval,
        batch_limit=limit,
        on_cycle=on_cycle,
    )


def start_scheduler(
    scheduler,
):

    result = {}

    def target():

        try:

            result["statistics"] = (
                scheduler.run_forever()
            )

        except Exception as exc:

            result["error"] = exc

    thread = threading.Thread(
        target=target,
        daemon=True,
    )

    thread.start()

    return thread, result


def stop_and_join(
    scheduler,
    thread,
):

    scheduler.request_stop()

    thread.join(
        timeout=5
    )

    assert not thread.is_alive(), (
        "Scheduler did not stop."
    )

def test_monitoring_failure_isolation():
    from application.research_recovery_scheduler import (
        ResearchRecoveryScheduler,
    )
    from application.research_recovery_worker import (
        RecoveryCycleSummary,
    )

    class FakeWorker:
        def __init__(self):
            self.calls = 0

        def run_once(self, limit, cancellation_event=None):
            self.calls += 1

            return RecoveryCycleSummary(
                scanned=1,
                resumed=1,
                paused=0,
                skipped=0,
                failed=0,
                outcomes=(),
            )

    worker = FakeWorker()

    scheduler = None

    def failing_monitor(summary):
        scheduler.request_stop()
        raise OSError(
            "Injected health-file failure"
        )

    scheduler = ResearchRecoveryScheduler(
        worker=worker,
        interval_seconds=0.1,
        batch_limit=7,
        on_cycle=failing_monitor,
    )

    stats = scheduler.run_forever()

    assert worker.calls == 1
    assert stats.cycles == 1
    assert stats.resumed == 1
    assert stats.failed == 0
    assert stats.cycle_errors == 0
    assert stats.monitor_errors == 1

    print(
        "TEST 10 - Monitoring failure does not "
        "invalidate recovery: PASSED"
    )


def main():

    print(
        "RESEARCH RECOVERY SCHEDULER"
    )
    print(
        "==========================="
    )

    #
    # Test 1 - Configuration validation
    #

    for invalid in (
        0,
        -1,
        0.01,
        86401,
        True,
        float("nan"),
        float("inf"),
    ):

        try:

            make_scheduler(
                interval=invalid
            )

        except ValueError:

            pass

        else:

            raise AssertionError(
                f"Invalid interval accepted: {invalid}"
            )

    print(
        "TEST 1 - Invalid polling intervals rejected: PASSED"
    )

    #
    # Test 2 - Batch limit validation
    #

    for invalid in (
        0,
        -1,
        1001,
        True,
        1.5,
    ):

        try:

            make_scheduler(
                limit=invalid
            )

        except ValueError:

            pass

        else:

            raise AssertionError(
                f"Invalid batch limit accepted: {invalid}"
            )

    print(
        "TEST 2 - Invalid batch limits rejected: PASSED"
    )

    #
    # Test 3 - Multiple cycles and statistics
    #

    service = FakeRecoveryService()

    completed = threading.Event()

    count = [0]

    scheduler = None

    def on_cycle(summary):

        count[0] += 1

        if count[0] == 3:

            scheduler.request_stop()
            completed.set()

    scheduler = make_scheduler(
        service=service,
        interval=0.1,
        on_cycle=on_cycle,
    )

    thread, result = start_scheduler(
        scheduler
    )

    assert completed.wait(
        timeout=5
    )

    thread.join(
        timeout=5
    )

    assert not thread.is_alive()
    assert "error" not in result

    statistics = result["statistics"]

    assert statistics.cycles == 3
    assert statistics.resumed == 3
    assert service.calls == 3

    print(
        "TEST 3 - Multiple recovery cycles and statistics: PASSED"
    )

    #
    # Test 4 - Stop interrupts polling wait
    #

    first_cycle = threading.Event()

    scheduler = make_scheduler(
        interval=10,
        on_cycle=lambda summary: first_cycle.set(),
    )

    thread, result = start_scheduler(
        scheduler
    )

    assert first_cycle.wait(
        timeout=5
    )

    started = time.monotonic()

    stop_and_join(
        scheduler,
        thread,
    )

    elapsed = time.monotonic() - started

    assert elapsed < 2
    assert "error" not in result

    print(
        "TEST 4 - Stop interrupts polling wait: PASSED"
    )

    #
    # Test 5 - Active cycle finishes before shutdown
    #

    entered = threading.Event()
    release = threading.Event()

    class BlockingService:

        def recover(self, limit=100, cancellation_event=None):

            entered.set()

            if not release.wait(timeout=5):

                raise TimeoutError(
                    "Blocking recovery was not released."
                )

            return []

    scheduler = make_scheduler(
        service=BlockingService(),
        interval=0.1,
    )

    thread, result = start_scheduler(
        scheduler
    )

    try:

        assert entered.wait(
            timeout=5
        )

        scheduler.request_stop()

        assert thread.is_alive()

    finally:

        release.set()

        thread.join(
            timeout=5
        )

    assert not thread.is_alive()
    assert "error" not in result
    assert result["statistics"].cycles == 1

    print(
        "TEST 5 - Active cycle completes before shutdown: PASSED"
    )

    #
    # Test 6 - Concurrent run_forever rejected
    #

    entered = threading.Event()
    release = threading.Event()

    class BlockingService2:

        def recover(self, limit=100, cancellation_event=None):

            entered.set()

            if not release.wait(timeout=5):

                raise TimeoutError()

            return []

    scheduler = make_scheduler(
        service=BlockingService2(),
    )

    thread, result = start_scheduler(
        scheduler
    )

    try:

        assert entered.wait(
            timeout=5
        )

        try:

            scheduler.run_forever()

        except RuntimeError as exc:

            assert "already running" in str(exc)

        else:

            raise AssertionError(
                "Overlapping scheduler execution accepted."
            )

    finally:

        scheduler.request_stop()
        release.set()

        thread.join(
            timeout=5
        )

    assert not thread.is_alive()
    assert "error" not in result

    print(
        "TEST 6 - Overlapping scheduler execution rejected: PASSED"
    )

    #
    # Test 7 - Cycle exception does not stop polling
    #

    class FailingOnceService:

        def __init__(self):

            self.calls = 0

        def recover(self, limit=100, cancellation_event=None):

            self.calls += 1

            if self.calls == 1:

                raise RuntimeError(
                    "Injected coordinator failure"
                )

            return []

    service = FailingOnceService()

    scheduler = None

    def stop_after_success(summary):

        scheduler.request_stop()

    scheduler = make_scheduler(
        service=service,
        interval=0.1,
        on_cycle=stop_after_success,
    )

    thread, result = start_scheduler(
        scheduler
    )

    thread.join(
        timeout=5
    )

    if thread.is_alive():

        stop_and_join(
            scheduler,
            thread,
        )

        raise AssertionError(
            "Scheduler did not recover from cycle error."
        )

    assert "error" not in result

    statistics = result["statistics"]

    assert statistics.cycle_errors == 1
    assert statistics.cycles == 1
    assert service.calls == 2

    print(
        "TEST 7 - Coordinator failure does not stop polling: PASSED"
    )

    #
    # Test 8 - Stop before start prevents execution
    #

    service = FakeRecoveryService()

    scheduler = make_scheduler(
        service=service
    )

    scheduler.request_stop()

    statistics = scheduler.run_forever()

    assert statistics.cycles == 0
    assert service.calls == 0

    print(
        "TEST 8 - Pre-requested stop prevents execution: PASSED"
    )

    #
    # Test 9 - Statistics accumulate mixed outcomes
    #

    class MixedService:

        def recover(self, limit=100, cancellation_event=None):

            return [
                RecoveryOutcome("a", "resumed"),
                RecoveryOutcome("b", "paused"),
                RecoveryOutcome("c", "skipped"),
                RecoveryOutcome("d", "failed", "Injected"),
            ]

    scheduler = None

    def stop_mixed(summary):

        scheduler.request_stop()

    scheduler = make_scheduler(
        service=MixedService(),
        on_cycle=stop_mixed,
    )

    statistics = scheduler.run_forever()

    assert statistics.cycles == 1
    assert statistics.resumed == 1
    assert statistics.paused == 1
    assert statistics.skipped == 1
    assert statistics.failed == 1
    assert statistics.cycle_errors == 0

    print(
        "TEST 9 - Mixed outcome statistics accumulated: PASSED"
    )

    test_monitoring_failure_isolation()

    print(
            "TEST 10 - Test Monitoring Failure Isolation: PASSED"
        )

    print()
    print("PASS")


if __name__ == "__main__":

    main()
