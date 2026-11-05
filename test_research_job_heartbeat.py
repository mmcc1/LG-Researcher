
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from application.research_job_heartbeat import (
    ResearchJobHeartbeat,
    ResearchJobLeaseLost,
)

from persistence.research_job_repository import (
    ResearchJobLease,
)


@pytest.fixture
def heartbeat():

    lease = ResearchJobLease(
        job_id="test-job",
        owner="test-worker",
        version=1,
        expires_at=datetime.now(timezone.utc),
    )

    session_factory = MagicMock()

    return ResearchJobHeartbeat(
        session_factory=session_factory,
        lease=lease,
        duration_seconds=120,
        renewal_interval_seconds=30,
    )


def test_heartbeat_rejects_invalid_duration():

    lease = ResearchJobLease(
        job_id="test-job",
        owner="test-worker",
        version=1,
        expires_at=datetime.now(timezone.utc),
    )

    with pytest.raises(ValueError):

        ResearchJobHeartbeat(
            session_factory=MagicMock(),
            lease=lease,
            duration_seconds=0,
        )


def test_heartbeat_rejects_invalid_interval():

    lease = ResearchJobLease(
        job_id="test-job",
        owner="test-worker",
        version=1,
        expires_at=datetime.now(timezone.utc),
    )

    with pytest.raises(ValueError):

        ResearchJobHeartbeat(
            session_factory=MagicMock(),
            lease=lease,
            duration_seconds=120,
            renewal_interval_seconds=120,
        )


def test_heartbeat_detects_rejected_renewal(
    heartbeat,
):

    heartbeat._stop_event.wait = MagicMock(
        side_effect=[False],
    )

    with patch(
        "application.research_job_heartbeat."
        "ResearchJobRepository"
    ) as repository_class:

        repository = repository_class.return_value

        repository.renew.return_value = None

        heartbeat._run()

    with pytest.raises(
        ResearchJobLeaseLost,
        match="renewal was rejected",
    ):

        heartbeat.check()


def test_heartbeat_detects_renewal_exception(
    heartbeat,
):

    heartbeat._stop_event.wait = MagicMock(
        side_effect=[False],
    )

    with patch(
        "application.research_job_heartbeat."
        "ResearchJobRepository"
    ) as repository_class:

        repository = repository_class.return_value

        repository.renew.side_effect = RuntimeError(
            "Database unavailable"
        )

        heartbeat._run()

    with pytest.raises(
        ResearchJobLeaseLost,
        match="Database unavailable",
    ):

        heartbeat.check()


def test_heartbeat_starts_only_once(
    heartbeat,
):

    heartbeat.start()

    try:

        with pytest.raises(
            RuntimeError,
            match="already been started",
        ):

            heartbeat.start()

    finally:

        heartbeat.stop()


def test_heartbeat_stop_propagates_lease_loss(
    heartbeat,
):

    heartbeat._failure = (
        "Research job lease renewal was rejected."
    )

    heartbeat._lost_event.set()

    with pytest.raises(
        ResearchJobLeaseLost,
    ):

        heartbeat.stop()
