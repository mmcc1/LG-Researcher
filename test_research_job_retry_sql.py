
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from persistence.database import engine

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
)

from persistence.models import UserAccount

from persistence.research_job_repository import (
    ResearchJobRepository,
)


TEST_DATABASE = "LGResearcher_Test"


@pytest.fixture
def test_environment():

    test_url = engine.url.set(
        database=TEST_DATABASE
    )

    assert test_url.database == TEST_DATABASE

    test_engine = create_engine(
        test_url,
        echo=False,
    )

    Session = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    user_id = str(uuid4())

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    with Session() as db:

        user = UserAccount(
            id=user_id,
            username=f"test_{user_id[:8]}",
            email=f"{user_id}@example.invalid",
            password_hash="integration-test-only",
            is_active=True,
            email_reports_enabled=False,
            created_at=now,
            last_login_at=None,
        )

        db.add(user)
        db.commit()

    try:

        yield Session, user_id

    finally:

        with Session() as db:

            params = {
                "user_id": user_id,
            }

            session_ids = db.execute(
                text("""
                    SELECT research_session_id
                    FROM dbo.research_jobs
                    WHERE user_id = :user_id
                      AND research_session_id IS NOT NULL
                """),
                params,
            ).scalars().all()

            db.execute(
                text("""
                    DELETE FROM dbo.research_job_questions
                    WHERE research_job_id IN (
                        SELECT id
                        FROM dbo.research_jobs
                        WHERE user_id = :user_id
                    )
                """),
                params,
            )

            db.execute(
                text("""
                    DELETE FROM dbo.research_jobs
                    WHERE user_id = :user_id
                """),
                params,
            )

            for session_id in session_ids:

                db.execute(
                    text("""
                        DELETE FROM dbo.research_sessions
                        WHERE id = :session_id
                    """),
                    {
                        "session_id": session_id,
                    },
                )

            db.execute(
                text("""
                    DELETE FROM dbo.users
                    WHERE id = :user_id
                """),
                params,
            )

            db.commit()

        test_engine.dispose()


def create_failed_job(
    Session,
    user_id,
):

    with Session() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic="Retry integration test",
            scope="Synthetic recovery scenario",
        )

        claimed = repository.claim_next(
            duration_seconds=120
        )

        assert claimed is not None
        assert claimed.job_id == job_id

        session_id = repository.associate_session(
            claimed.lease
        )

        assert repository.fail(
            lease=claimed.lease,
            error="Synthetic execution failure",
        )

    return job_id, session_id


def get_job_state(
    Session,
    job_id,
):

    with Session() as db:

        row = db.execute(
            text("""
                SELECT
                    status,
                    research_session_id,
                    execution_owner,
                    lease_expires_at,
                    lease_version,
                    last_error
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job_id,
            },
        ).one()

        return {
            "status": row[0],
            "session_id": row[1],
            "owner": row[2],
            "expires_at": row[3],
            "version": row[4],
            "error": row[5],
        }


def test_failed_job_can_be_requeued(
    test_environment,
):

    Session, user_id = test_environment

    job_id, session_id = create_failed_job(
        Session,
        user_id,
    )

    original = get_job_state(
        Session,
        job_id,
    )

    assert original["status"] == "failed"
    assert original["error"] is not None

    with Session() as db:

        repository = ResearchJobRepository(db)

        assert repository.retry_failed(
            job_id=job_id,
            user_id=user_id,
        )

    updated = get_job_state(
        Session,
        job_id,
    )

    assert updated["status"] == "queued"
    assert updated["session_id"] == session_id
    assert updated["owner"] is None
    assert updated["expires_at"] is None
    assert updated["error"] is None
    assert updated["version"] == original["version"]


def test_retry_preserves_session_when_claimed(
    test_environment,
):

    Session, user_id = test_environment

    job_id, session_id = create_failed_job(
        Session,
        user_id,
    )

    with Session() as db:

        repository = ResearchJobRepository(db)

        assert repository.retry_failed(
            job_id,
            user_id,
        )

        claimed = repository.claim_next()

        assert claimed is not None
        assert claimed.job_id == job_id

        associated_session_id = (
            repository.associate_session(
                claimed.lease
            )
        )

        assert associated_session_id == session_id

        assert repository.fail(
            lease=claimed.lease,
            error="Synthetic retry interruption",
        )

    with Session() as db:

        count = db.execute(
            text("""
                SELECT COUNT(*)
                FROM dbo.research_sessions
                WHERE id = :session_id
            """),
            {
                "session_id": session_id,
            },
        ).scalar_one()

        assert count == 1


def test_retry_rejects_wrong_user(
    test_environment,
):

    Session, user_id = test_environment

    job_id, _ = create_failed_job(
        Session,
        user_id,
    )

    with Session() as db:

        repository = ResearchJobRepository(db)

        assert not repository.retry_failed(
            job_id=job_id,
            user_id=str(uuid4()),
        )

    assert get_job_state(
        Session,
        job_id,
    )["status"] == "failed"


def test_retry_is_not_repeatable_while_queued(
    test_environment,
):

    Session, user_id = test_environment

    job_id, _ = create_failed_job(
        Session,
        user_id,
    )

    with Session() as db:

        repository = ResearchJobRepository(db)

        assert repository.retry_failed(
            job_id,
            user_id,
        )

        assert not repository.retry_failed(
            job_id,
            user_id,
        )


def test_retry_rejects_paused_session(
    test_environment,
):

    Session, user_id = test_environment

    job_id, session_id = create_failed_job(
        Session,
        user_id,
    )

    with Session() as db:

        db.execute(
            text("""
                UPDATE dbo.research_sessions
                SET pause_requested = 1
                WHERE id = :session_id
            """),
            {
                "session_id": session_id,
            },
        )

        db.commit()

    with Session() as db:

        repository = ResearchJobRepository(db)

        assert not repository.retry_failed(
            job_id,
            user_id,
        )

    assert get_job_state(
        Session,
        job_id,
    )["status"] == "failed"


def test_retry_rejects_active_session_lease(
    test_environment,
):

    Session, user_id = test_environment

    job_id, session_id = create_failed_job(
        Session,
        user_id,
    )

    with Session() as db:

        lease_repository = (
            ExecutionLeaseRepository(db)
        )

        lease = lease_repository.acquire(
            session_id=session_id,
            duration_seconds=120,
        )

        assert lease is not None

    try:

        with Session() as db:

            repository = ResearchJobRepository(db)

            assert not repository.retry_failed(
                job_id,
                user_id,
            )

        assert get_job_state(
            Session,
            job_id,
        )["status"] == "failed"

    finally:

        with Session() as db:

            assert ExecutionLeaseRepository(
                db
            ).release(
                lease
            )


def test_retry_rejects_active_job_owner(
    test_environment,
):

    Session, user_id = test_environment

    job_id, _ = create_failed_job(
        Session,
        user_id,
    )

    with Session() as db:

        db.execute(
            text("""
                UPDATE dbo.research_jobs
                SET execution_owner = :owner
                WHERE id = :job_id
            """),
            {
                "owner": str(uuid4()),
                "job_id": job_id,
            },
        )

        db.commit()

    with Session() as db:

        repository = ResearchJobRepository(db)

        assert not repository.retry_failed(
            job_id,
            user_id,
        )

    assert get_job_state(
        Session,
        job_id,
    )["status"] == "failed"


def test_completed_session_job_can_be_finalized(
    test_environment,
):

    Session, user_id = test_environment

    job_id, session_id = create_failed_job(
        Session,
        user_id,
    )

    with Session() as db:

        db.execute(
            text("""
                UPDATE dbo.research_sessions
                SET status = 'completed'
                WHERE id = :session_id
            """),
            {
                "session_id": session_id,
            },
        )

        db.commit()

    with Session() as db:

        repository = ResearchJobRepository(db)

        assert repository.retry_failed(
            job_id,
            user_id,
        )

        claimed = repository.claim_next()

        assert claimed is not None
        assert claimed.job_id == job_id

        assert repository.associate_session(
            claimed.lease
        ) == session_id

        assert repository.complete(
            claimed.lease
        )

    updated = get_job_state(
        Session,
        job_id,
    )

    assert updated["status"] == "completed"
    assert updated["session_id"] == session_id
    assert updated["error"] is None
