
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from persistence.research_job_repository import (
    ResearchJobLease,
    ResearchJobRepository,
)


def test_submit_creates_queued_job():

    db = MagicMock()

    repository = ResearchJobRepository(db)

    job_id = repository.submit(
        user_id="user-123",
        topic="Quantum computing and Bitcoin",
        scope="Cryptographic risks",
    )

    assert job_id

    db.add.assert_called_once()
    db.commit.assert_called_once()

    job = db.add.call_args.args[0]

    assert job.id == job_id
    assert job.user_id == "user-123"
    assert job.topic == "Quantum computing and Bitcoin"
    assert job.scope == "Cryptographic risks"
    assert job.status == "queued"
    assert job.research_session_id is None
    assert job.lease_version == 0


def test_submit_rejects_empty_topic():

    db = MagicMock()

    repository = ResearchJobRepository(db)

    with pytest.raises(ValueError):

        repository.submit(
            user_id="user-123",
            topic=" ",
        )

    db.add.assert_not_called()


def test_submit_rolls_back_on_failure():

    db = MagicMock()

    db.commit.side_effect = RuntimeError(
        "Database unavailable"
    )

    repository = ResearchJobRepository(db)

    with pytest.raises(RuntimeError):

        repository.submit(
            user_id="user-123",
            topic="Research topic",
        )

    db.rollback.assert_called_once()


def test_claim_next_returns_job_and_lease():

    db = MagicMock()

    expiry = datetime(2026, 11, 5, 12, 0, 0)

    db.execute.return_value.first.return_value = (
        "job-123",
        "user-123",
        "Research topic",
        "Research scope",
        None,
        1,
        expiry,
    )

    repository = ResearchJobRepository(db)

    claimed = repository.claim_next()

    assert claimed is not None

    assert claimed.job_id == "job-123"
    assert claimed.user_id == "user-123"
    assert claimed.topic == "Research topic"
    assert claimed.scope == "Research scope"
    assert claimed.research_session_id is None

    assert claimed.lease.job_id == "job-123"
    assert claimed.lease.version == 1
    assert claimed.lease.expires_at == expiry

    db.commit.assert_called_once()


def test_claim_next_returns_none_when_empty():

    db = MagicMock()

    db.execute.return_value.first.return_value = None

    repository = ResearchJobRepository(db)

    claimed = repository.claim_next()

    assert claimed is None

    db.commit.assert_called_once()


def test_claim_next_rejects_invalid_duration():

    db = MagicMock()

    repository = ResearchJobRepository(db)

    for duration in (0, -1, 86401, True):

        with pytest.raises(ValueError):

            repository.claim_next(
                duration_seconds=duration
            )

    db.execute.assert_not_called()


def test_renew_returns_updated_lease():

    db = MagicMock()

    expiry = datetime(2026, 11, 5, 13, 0, 0)

    db.execute.return_value.first.return_value = (
        expiry,
    )

    repository = ResearchJobRepository(db)

    lease = ResearchJobLease(
        job_id="job-123",
        owner="owner-123",
        version=2,
        expires_at=datetime(2026, 11, 5, 12, 0, 0),
    )

    renewed = repository.renew(
        lease,
        duration_seconds=120,
    )

    assert renewed is not None

    assert renewed.job_id == lease.job_id
    assert renewed.owner == lease.owner
    assert renewed.version == lease.version
    assert renewed.expires_at == expiry

    db.commit.assert_called_once()


def test_renew_returns_none_when_rejected():

    db = MagicMock()

    db.execute.return_value.first.return_value = None

    repository = ResearchJobRepository(db)

    lease = ResearchJobLease(
        job_id="job-123",
        owner="owner-123",
        version=2,
        expires_at=datetime(2026, 11, 5, 12, 0, 0),
    )

    renewed = repository.renew(lease)

    assert renewed is None


def test_release_returns_true_when_successful():

    db = MagicMock()

    db.execute.return_value.first.return_value = (
        "job-123",
    )

    repository = ResearchJobRepository(db)

    lease = ResearchJobLease(
        job_id="job-123",
        owner="owner-123",
        version=2,
        expires_at=datetime(2026, 11, 5, 12, 0, 0),
    )

    released = repository.release(lease)

    assert released is True

    db.commit.assert_called_once()


def test_release_returns_false_for_stale_lease():

    db = MagicMock()

    db.execute.return_value.first.return_value = None

    repository = ResearchJobRepository(db)

    lease = ResearchJobLease(
        job_id="job-123",
        owner="old-owner",
        version=1,
        expires_at=datetime(2026, 11, 5, 12, 0, 0),
    )

    released = repository.release(lease)

    assert released is False


def test_claim_next_rolls_back_on_database_failure():

    db = MagicMock()

    db.execute.side_effect = RuntimeError(
        "SQL Server unavailable"
    )

    repository = ResearchJobRepository(db)

    with pytest.raises(RuntimeError):

        repository.claim_next()

    db.rollback.assert_called_once()
