
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from sqlalchemy import text

from application.research_job_worker import (
    ResearchJobNotCompleted,
    ResearchJobWorker,
)

from persistence.research_job_repository import (
    ResearchJobRepository,
)

from test_research_job_repository_sql import (
    cleanup_associated_session,
    test_environment,
)


@pytest.fixture
def worker_environment(test_environment):

    Session, user_id = test_environment

    workflow_service = MagicMock()

    worker = ResearchJobWorker(
        session_factory=Session,
        workflow_service=workflow_service,
        lease_duration_seconds=120,
        heartbeat_interval_seconds=30,
    )

    job_ids = []

    yield {
        "Session": Session,
        "user_id": user_id,
        "worker": worker,
        "workflow_service": workflow_service,
        "job_ids": job_ids,
    }

    with Session() as db:

        rows = db.execute(
            text("""
                SELECT id, research_session_id
                FROM dbo.research_jobs
                WHERE user_id = :user_id
                  AND research_session_id IS NOT NULL
            """),
            {
                "user_id": user_id,
            },
        ).all()

    for job_id, session_id in rows:

        cleanup_associated_session(
            Session=Session,
            job_id=job_id,
            session_id=session_id,
        )


def submit_job(
    environment,
    topic,
):

    Session = environment["Session"]
    user_id = environment["user_id"]

    with Session() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic=topic,
            scope="Worker SQL integration test",
        )

    environment["job_ids"].append(job_id)

    return job_id


def get_job(
    environment,
    job_id,
):

    Session = environment["Session"]

    with Session() as db:

        return db.execute(
            text("""
                SELECT
                    status,
                    research_session_id,
                    execution_owner,
                    lease_expires_at,
                    lease_version,
                    completed_at,
                    last_error
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job_id,
            },
        ).one()


def get_session_status(
    environment,
    session_id,
):

    Session = environment["Session"]

    with Session() as db:

        return db.execute(
            text("""
                SELECT status
                FROM dbo.research_sessions
                WHERE id = :session_id
            """),
            {
                "session_id": session_id,
            },
        ).scalar_one()


def set_session_status(
    environment,
    session_id,
    status,
):

    Session = environment["Session"]

    with Session() as db:

        db.execute(
            text("""
                UPDATE dbo.research_sessions
                SET status = :status,
                    updated_at = SYSUTCDATETIME()
                WHERE id = :session_id
            """),
            {
                "session_id": session_id,
                "status": status,
            },
        )

        db.commit()


def expire_job_lease(
    environment,
    job_id,
):

    Session = environment["Session"]

    with Session() as db:

        db.execute(
            text("""
                UPDATE dbo.research_jobs
                SET lease_expires_at = DATEADD(
                    second,
                    -10,
                    SYSUTCDATETIME()
                )
                WHERE id = :job_id
            """),
            {
                "job_id": job_id,
            },
        )

        db.commit()


def test_sql_worker_completes_job(
    worker_environment,
):

    environment = worker_environment

    job_id = submit_job(
        environment,
        "Worker normal execution",
    )

    workflow_service = environment["workflow_service"]

    def execute_existing(
        session_id,
        execution_guard,
    ):

        execution_guard()

        assert get_session_status(
            environment,
            session_id,
        ) == "created"

        set_session_status(
            environment,
            session_id,
            "completed",
        )

        execution_guard()

    workflow_service.execute_existing.side_effect = (
        execute_existing
    )

    result = environment["worker"].process_next()

    assert result == job_id

    row = get_job(
        environment,
        job_id,
    )

    assert row[0] == "completed"
    assert row[1] is not None
    assert row[2] is None
    assert row[3] is None
    assert row[5] is not None
    assert row[6] is None

    assert get_session_status(
        environment,
        row[1],
    ) == "completed"

    workflow_service.execute_existing.assert_called_once()


def test_sql_worker_recovers_completed_session(
    worker_environment,
):

    environment = worker_environment

    job_id = submit_job(
        environment,
        "Worker completed-session recovery",
    )

    Session = environment["Session"]

    with Session() as db:

        repository = ResearchJobRepository(db)

        original = repository.claim_next()

        assert original is not None
        assert original.job_id == job_id

        session_id = repository.associate_session(
            original.lease
        )

    set_session_status(
        environment,
        session_id,
        "completed",
    )

    expire_job_lease(
        environment,
        job_id,
    )

    result = environment["worker"].process_next()

    assert result == job_id

    row = get_job(
        environment,
        job_id,
    )

    assert row[0] == "completed"
    assert row[1] == session_id
    assert row[4] > original.lease.version

    environment[
        "workflow_service"
    ].execute_existing.assert_not_called()

    with Session() as db:

        repository = ResearchJobRepository(db)

        assert repository.complete(
            original.lease
        ) is False

        assert repository.fail(
            lease=original.lease,
            error="Stale worker failure",
        ) is False


def test_sql_worker_resumes_existing_session(
    worker_environment,
):

    environment = worker_environment

    job_id = submit_job(
        environment,
        "Worker interrupted-session recovery",
    )

    Session = environment["Session"]

    with Session() as db:

        repository = ResearchJobRepository(db)

        original = repository.claim_next()

        assert original is not None

        session_id = repository.associate_session(
            original.lease
        )

    set_session_status(
        environment,
        session_id,
        "planning",
    )

    expire_job_lease(
        environment,
        job_id,
    )

    workflow_service = environment["workflow_service"]

    def execute_existing(
        session_id,
        execution_guard,
    ):

        assert session_id == get_job(
            environment,
            job_id,
        )[1]

        assert get_session_status(
            environment,
            session_id,
        ) == "planning"

        execution_guard()

        set_session_status(
            environment,
            session_id,
            "completed",
        )

    workflow_service.execute_existing.side_effect = (
        execute_existing
    )

    result = environment["worker"].process_next()

    assert result == job_id

    row = get_job(
        environment,
        job_id,
    )

    assert row[0] == "completed"
    assert row[1] == session_id
    assert row[4] > original.lease.version

    workflow_service.execute_existing.assert_called_once()


def test_sql_worker_records_execution_failure(
    worker_environment,
):

    environment = worker_environment

    job_id = submit_job(
        environment,
        "Worker execution failure",
    )

    environment[
        "workflow_service"
    ].execute_existing.side_effect = RuntimeError(
        "Simulated research failure."
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated research failure",
    ):

        environment["worker"].process_next()

    row = get_job(
        environment,
        job_id,
    )

    assert row[0] == "failed"
    assert row[1] is not None
    assert row[2] is None
    assert row[3] is None
    assert row[6] == "Simulated research failure."


def test_sql_worker_rejects_incomplete_execution(
    worker_environment,
):

    environment = worker_environment

    job_id = submit_job(
        environment,
        "Worker incomplete execution",
    )

    with pytest.raises(
        ResearchJobNotCompleted,
        match="could not be finalized",
    ):

        environment["worker"].process_next()

    row = get_job(
        environment,
        job_id,
    )

    assert row[0] == "claimed"
    assert row[1] is not None
    assert row[2] is not None
    assert row[3] is not None
    assert row[5] is None

    assert get_session_status(
        environment,
        row[1],
    ) == "created"
