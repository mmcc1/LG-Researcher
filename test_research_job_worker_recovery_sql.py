
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from application.research_job_worker import (
    ResearchJobWorker,
)

from persistence.database import engine

from persistence.models import UserAccount

from persistence.research_job_repository import (
    ResearchJobRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


TEST_DATABASE = "LGResearcher_Test"


class DeterministicWorkflowService:

    def __init__(
        self,
        session_factory,
        fail=False,
    ):

        self.session_factory = session_factory
        self.fail = fail
        self.calls = []

    def execute_existing(
        self,
        session_id,
        execution_guard=None,
    ):

        self.calls.append(session_id)

        if execution_guard is not None:
            execution_guard()

        if self.fail:

            raise RuntimeError(
                "Synthetic workflow execution failure."
            )

        with self.session_factory() as db:

            repository = ResearchSessionRepository(
                db
            )

            repository.set_status(
                session_id=session_id,
                status="completed",
            )

        if execution_guard is not None:
            execution_guard()


@pytest.fixture
def test_environment():

    test_url = engine.url.set(
        database=TEST_DATABASE
    )

    if test_url.database != TEST_DATABASE:

        raise RuntimeError(
            "Invalid integration test database."
        )

    test_engine = create_engine(
        test_url,
        echo=False,
    )

    Session = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    with test_engine.connect() as connection:

        database_name = connection.execute(
            text("SELECT DB_NAME()")
        ).scalar_one()

        if database_name != TEST_DATABASE:

            test_engine.dispose()

            raise RuntimeError(
                "Integration test database mismatch. "
                f"Connected to: {database_name}"
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

        repository = ResearchJobRepository(
            db
        )

        job_id = repository.submit(
            user_id=user_id,
            topic="Worker recovery integration test",
            scope="Synthetic workflow recovery scenario",
        )

        claimed = repository.claim_next(
            duration_seconds=120
        )

        assert claimed is not None

        assert claimed.job_id == job_id

        session_id = repository.associate_session(
            claimed.lease
        )

        failed = repository.fail(
            lease=claimed.lease,
            error="Synthetic initial execution failure.",
        )

        assert failed is True

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


def get_session_status(
    Session,
    session_id,
):

    with Session() as db:

        repository = ResearchSessionRepository(
            db
        )

        research_session = repository.get(
            session_id
        )

        assert research_session is not None

        return research_session.status


def test_worker_recovers_failed_job(
    test_environment,
):

    Session, user_id = test_environment

    job_id, session_id = create_failed_job(
        Session,
        user_id,
    )

    original_state = get_job_state(
        Session,
        job_id,
    )

    assert original_state["status"] == "failed"

    with Session() as db:

        repository = ResearchJobRepository(
            db
        )

        retried = repository.retry_failed(
            job_id=job_id,
            user_id=user_id,
        )

        assert retried is True

    queued_state = get_job_state(
        Session,
        job_id,
    )

    assert queued_state["status"] == "queued"

    assert queued_state["session_id"] == session_id

    workflow_service = DeterministicWorkflowService(
        session_factory=Session,
    )

    worker = ResearchJobWorker(
        session_factory=Session,
        workflow_service=workflow_service,
        lease_duration_seconds=120,
        heartbeat_interval_seconds=30.0,
    )

    processed_job_id = worker.process_next()

    assert processed_job_id == job_id

    assert workflow_service.calls == [
        session_id
    ]

    completed_state = get_job_state(
        Session,
        job_id,
    )

    assert completed_state["status"] == "completed"

    assert completed_state["session_id"] == session_id

    assert completed_state["owner"] is None

    assert get_session_status(
        Session,
        session_id,
    ) == "completed"


def test_worker_marks_job_failed_when_workflow_fails(
    test_environment,
):

    Session, user_id = test_environment

    job_id, session_id = create_failed_job(
        Session,
        user_id,
    )

    with Session() as db:

        repository = ResearchJobRepository(
            db
        )

        retried = repository.retry_failed(
            job_id=job_id,
            user_id=user_id,
        )

        assert retried is True

    workflow_service = DeterministicWorkflowService(
        session_factory=Session,
        fail=True,
    )

    worker = ResearchJobWorker(
        session_factory=Session,
        workflow_service=workflow_service,
        lease_duration_seconds=120,
        heartbeat_interval_seconds=30.0,
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic workflow execution failure",
    ):

        worker.process_next()

    assert workflow_service.calls == [
        session_id
    ]

    failed_state = get_job_state(
        Session,
        job_id,
    )

    assert failed_state["status"] == "failed"

    assert failed_state["session_id"] == session_id

    assert (
        "Synthetic workflow execution failure"
        in failed_state["error"]
    )

    assert get_session_status(
        Session,
        session_id,
    ) != "completed"


def test_worker_finalizes_already_completed_session(
    test_environment,
):

    Session, user_id = test_environment

    job_id, session_id = create_failed_job(
        Session,
        user_id,
    )

    with Session() as db:

        repository = ResearchSessionRepository(
            db
        )

        repository.set_status(
            session_id=session_id,
            status="completed",
        )

    with Session() as db:

        repository = ResearchJobRepository(
            db
        )

        retried = repository.retry_failed(
            job_id=job_id,
            user_id=user_id,
        )

        assert retried is True

    workflow_service = DeterministicWorkflowService(
        session_factory=Session,
        fail=True,
    )

    worker = ResearchJobWorker(
        session_factory=Session,
        workflow_service=workflow_service,
        lease_duration_seconds=120,
        heartbeat_interval_seconds=30.0,
    )

    processed_job_id = worker.process_next()

    assert processed_job_id == job_id

    assert workflow_service.calls == []

    completed_state = get_job_state(
        Session,
        job_id,
    )

    assert completed_state["status"] == "completed"

    assert completed_state["session_id"] == session_id
