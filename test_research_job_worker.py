
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from application.research_job_heartbeat import (
    ResearchJobLeaseLost,
)

from application.research_job_worker import (
    ResearchJobNotCompleted,
    ResearchJobWorker,
)

from persistence.research_job_repository import (
    ResearchJobLease,
    ResearchJobLeaseUnavailable,
)


@pytest.fixture
def worker_environment():

    lease = ResearchJobLease(
        job_id="job-123",
        owner="worker-123",
        version=1,
        expires_at=(
            datetime.now(timezone.utc)
            + timedelta(minutes=5)
        ),
    )

    claimed = SimpleNamespace(
        job_id="job-123",
        user_id="user-123",
        topic="Quantum computing and Bitcoin",
        scope="Cryptographic risks",
        research_session_id=None,
        lease=lease,
    )

    session_factory = MagicMock()

    workflow_service = MagicMock()

    worker = ResearchJobWorker(
        session_factory=session_factory,
        workflow_service=workflow_service,
        lease_duration_seconds=120,
        heartbeat_interval_seconds=30,
    )

    with (
        patch(
            "application.research_job_worker."
            "ResearchJobRepository"
        ) as repository_class,
        patch(
            "application.research_job_worker."
            "ResearchJobHeartbeat"
        ) as heartbeat_class,
        patch(
            "application.research_job_worker."
            "ResearchSessionRepository"
        ) as session_repository_class,
    ):

        session_repository = session_repository_class.return_value

        session_repository.get.return_value = SimpleNamespace(
            id="session-123",
            status="created",
        )
        repository = repository_class.return_value

        repository.claim_next.return_value = claimed
        repository.associate_session.return_value = "session-123"
        repository.complete.return_value = True
        repository.fail.return_value = True

        heartbeat = heartbeat_class.return_value

        heartbeat.lease = lease

        yield SimpleNamespace(
            worker=worker,
            lease=lease,
            claimed=claimed,
            repository=repository,
            heartbeat=heartbeat,
            workflow_service=workflow_service,
            heartbeat_class=heartbeat_class,
        )


def test_worker_returns_none_when_queue_empty(
    worker_environment,
):

    environment = worker_environment

    environment.repository.claim_next.return_value = None

    result = environment.worker.process_next()

    assert result is None

    environment.heartbeat.start.assert_not_called()

    environment.workflow_service.execute_existing.assert_not_called()


def test_worker_completes_research_job(
    worker_environment,
):

    environment = worker_environment

    result = environment.worker.process_next()

    assert result == "job-123"

    environment.repository.claim_next.assert_called_once_with(
        duration_seconds=120,
    )

    environment.repository.associate_session.assert_called_once_with(
        environment.lease
    )

    environment.workflow_service.execute_existing.assert_called_once_with(
        session_id="session-123",
        execution_guard=environment.heartbeat.check,
    )

    environment.repository.complete.assert_called_once_with(
        environment.lease
    )

    environment.repository.fail.assert_not_called()

    environment.heartbeat.start.assert_called_once()

    environment.heartbeat.stop.assert_called_once()


def test_worker_reuses_existing_research_session(
    worker_environment,
):

    environment = worker_environment

    environment.claimed.research_session_id = (
        "existing-session-123"
    )

    environment.repository.associate_session.return_value = (
        "existing-session-123"
    )

    result = environment.worker.process_next()

    assert result == "job-123"

    environment.repository.associate_session.assert_called_once_with(
        environment.lease
    )

    environment.workflow_service.execute_existing.assert_called_once_with(
        session_id="existing-session-123",
        execution_guard=environment.heartbeat.check,
    )


def test_worker_records_execution_failure(
    worker_environment,
):

    environment = worker_environment

    environment.workflow_service.execute_existing.side_effect = (
        RuntimeError(
            "Research execution failed."
        )
    )

    with pytest.raises(
        RuntimeError,
        match="Research execution failed",
    ):

        environment.worker.process_next()

    environment.repository.fail.assert_called_once_with(
        lease=environment.lease,
        error="Research execution failed.",
    )

    environment.repository.complete.assert_not_called()

    environment.heartbeat.stop.assert_called_once()


def test_worker_does_not_finalize_after_lease_loss(
    worker_environment,
):

    environment = worker_environment

    environment.workflow_service.execute_existing.side_effect = (
        ResearchJobLeaseLost(
            "Research job lease expired."
        )
    )

    with pytest.raises(
        ResearchJobLeaseLost,
    ):

        environment.worker.process_next()

    environment.repository.complete.assert_not_called()

    environment.repository.fail.assert_not_called()

    environment.heartbeat.stop.assert_called_once()


def test_worker_does_not_fail_job_after_association_lease_loss(
    worker_environment,
):

    environment = worker_environment

    environment.repository.associate_session.side_effect = (
        ResearchJobLeaseUnavailable(
            "Job ownership changed."
        )
    )

    with pytest.raises(
        ResearchJobLeaseUnavailable,
    ):

        environment.worker.process_next()

    environment.workflow_service.execute_existing.assert_not_called()

    environment.repository.complete.assert_not_called()

    environment.repository.fail.assert_not_called()

    environment.heartbeat.stop.assert_called_once()


def test_worker_rejects_incomplete_research_session(
    worker_environment,
):

    environment = worker_environment

    environment.repository.complete.return_value = False

    with pytest.raises(
        ResearchJobNotCompleted,
        match="could not be finalized",
    ):

        environment.worker.process_next()

    environment.repository.fail.assert_not_called()

    environment.heartbeat.stop.assert_called_once()


def test_worker_keeps_heartbeat_active_until_finalization(
    worker_environment,
):

    environment = worker_environment

    events = []

    def record_complete(lease):

        events.append("complete")

        return True

    def record_stop():

        events.append("stop")

    environment.repository.complete.side_effect = (
        record_complete
    )

    environment.heartbeat.stop.side_effect = (
        record_stop
    )

    result = environment.worker.process_next()

    assert result == "job-123"

    assert events == [
        "complete",
        "stop",
    ]



def test_worker_finalizes_already_completed_session(
    worker_environment,
):

    environment = worker_environment

    with patch(
        "application.research_job_worker."
        "ResearchSessionRepository"
    ) as session_repository_class:

        session_repository = session_repository_class.return_value

        session_repository.get.return_value = SimpleNamespace(
            id="session-123",
            status="completed",
        )

        result = environment.worker.process_next()

    assert result == "job-123"

    environment.workflow_service.execute_existing.assert_not_called()

    environment.repository.complete.assert_called_once_with(
        environment.lease
    )

    environment.repository.fail.assert_not_called()
