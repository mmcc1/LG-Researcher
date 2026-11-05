import logging
import threading

from types import SimpleNamespace
from unittest.mock import patch

from application.research_recovery_service import (
    ResearchRecoveryService,
    RecoveryOutcome,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseUnavailable,
)

from persistence.research_session_repository import (
    RecoveryNotEligible,
)


logging.disable(logging.CRITICAL)


def check(condition, description):
    assert condition, description
    print(f"{description}: PASSED")


class FakeWorkflowService:

    def __init__(self):
        self.calls = []
        self.results = {}
        self.exceptions = {}
        self.on_recover = None

    def recover(self, session_id):
        self.calls.append(session_id)

        if self.on_recover is not None:
            self.on_recover(session_id)

        if session_id in self.exceptions:
            raise self.exceptions[session_id]

        return SimpleNamespace(
            graph_result=self.results.get(
                session_id, {}
            )
        )


class FakeRecoveryService(ResearchRecoveryService):

    def __init__(self, candidates=None):
        self.workflow = FakeWorkflowService()

        super().__init__(
            workflow_service=self.workflow,
            session_factory=None,
        )

        self.candidates = list(candidates or [])
        self.discovery_calls = []

    def find_candidates(self, limit=100):
        self.discovery_calls.append(limit)
        return self.candidates[:limit]


def test_candidate_discovery():
    service = FakeRecoveryService(
        ["s1", "s2", "s3"]
    )

    outcomes = service.recover(limit=2)

    check(
        service.discovery_calls == [2],
        "TEST 1A - Batch limit forwarded",
    )

    check(
        [o.session_id for o in outcomes] == ["s1", "s2"],
        "TEST 1B - Candidate limit respected",
    )


def test_successful_recovery():
    service = FakeRecoveryService()

    outcome = service.recover_session("s1")

    check(
        outcome == RecoveryOutcome(
            session_id="s1",
            status="resumed",
        ),
        "TEST 2 - Successful session recovery",
    )


def test_paused_recovery():
    service = FakeRecoveryService()
    service.workflow.results["s1"] = {
        "pause_requested": True
    }

    outcome = service.recover_session("s1")

    check(
        outcome.status == "paused",
        "TEST 3 - Paused workflow detected",
    )


def test_lease_unavailable():
    service = FakeRecoveryService()

    # Use a real instance of the repository exception.
    service.workflow.exceptions["s1"] = (
        ExecutionLeaseUnavailable("Lease unavailable")
    )

    outcome = service.recover_session("s1")

    check(
        outcome.status == "skipped",
        "TEST 4 - Unavailable execution lease skipped",
    )


def test_recovery_not_eligible():
    service = FakeRecoveryService()

    service.workflow.exceptions["s1"] = (
        RecoveryNotEligible("Not eligible")
    )

    outcome = service.recover_session("s1")

    check(
        outcome.status == "skipped",
        "TEST 5 - Ineligible recovery skipped",
    )


def test_unexpected_failure():
    service = FakeRecoveryService()

    service.workflow.exceptions["s1"] = (
        RuntimeError("Injected workflow failure")
    )

    outcome = service.recover_session("s1")

    check(
        outcome.status == "failed"
        and outcome.error == "Injected workflow failure",
        "TEST 6 - Unexpected failure recorded",
    )


def test_candidate_order():
    service = FakeRecoveryService(
        ["s3", "s1", "s2"]
    )

    outcomes = service.recover()

    check(
        service.workflow.calls == ["s3", "s1", "s2"]
        and [o.session_id for o in outcomes]
        == ["s3", "s1", "s2"],
        "TEST 7 - Candidate order preserved",
    )


def test_pre_cancelled_recovery():
    service = FakeRecoveryService(
        ["s1", "s2"]
    )

    event = threading.Event()
    event.set()

    outcomes = service.recover(
        cancellation_event=event
    )

    check(
        outcomes == []
        and service.discovery_calls == []
        and service.workflow.calls == [],
        "TEST 8 - Cancellation prevents discovery",
    )


def test_cancellation_between_sessions():
    service = FakeRecoveryService(
        ["s1", "s2", "s3"]
    )

    event = threading.Event()

    def request_shutdown(session_id):
        if session_id == "s1":
            event.set()

    service.workflow.on_recover = request_shutdown

    outcomes = service.recover(
        cancellation_event=event
    )

    check(
        service.workflow.calls == ["s1"]
        and len(outcomes) == 1,
        "TEST 9 - Cancellation stops subsequent sessions",
    )


def test_partial_outcomes_preserved():
    service = FakeRecoveryService(
        ["s1", "s2", "s3"]
    )

    service.workflow.results["s1"] = {
        "pause_requested": True
    }

    event = threading.Event()

    def request_shutdown(session_id):
        if session_id == "s2":
            event.set()

    service.workflow.on_recover = request_shutdown

    outcomes = service.recover(
        cancellation_event=event
    )

    check(
        [(o.session_id, o.status) for o in outcomes]
        == [
            ("s1", "paused"),
            ("s2", "resumed"),
        ],
        "TEST 10 - Partial outcomes preserved",
    )


def main():
    print()
    print("RESEARCH RECOVERY SERVICE")
    print("=========================")

    test_candidate_discovery()
    test_successful_recovery()
    test_paused_recovery()
    test_lease_unavailable()
    test_recovery_not_eligible()
    test_unexpected_failure()
    test_candidate_order()
    test_pre_cancelled_recovery()
    test_cancellation_between_sessions()
    test_partial_outcomes_preserved()

    print()
    print("RESEARCH RECOVERY SERVICE: ALL TESTS PASSED")


if __name__ == "__main__":
    main()
