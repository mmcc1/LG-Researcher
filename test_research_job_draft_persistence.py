
import os

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
from uuid import uuid4

import pytest

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from persistence.database import SessionLocal
from persistence.models import ResearchJob
from persistence.research_job_repository import (
    ResearchJobRepository,
)


pytestmark = pytest.mark.skipif(
    os.environ.get(
        "RUN_SQLSERVER_INTEGRATION_TESTS"
    ) != "1",
    reason="SQL Server integration tests are disabled.",
)


@pytest.fixture
def test_users():

    first_user_id = str(uuid4())
    second_user_id = str(uuid4())

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    with SessionLocal() as db:

        for user_id in (
            first_user_id,
            second_user_id,
        ):

            db.execute(
                text("""
                    INSERT INTO dbo.users (
                        id,
                        username,
                        email,
                        password_hash,
                        is_active,
                        email_reports_enabled,
                        created_at
                    )
                    VALUES (
                        :user_id,
                        :username,
                        :email,
                        :password_hash,
                        1,
                        0,
                        :created_at
                    )
                """),
                {
                    "user_id": user_id,
                    "username": user_id,
                    "email": f"{user_id}@example.invalid",
                    "password_hash": "integration-test-only",
                    "created_at": now,
                },
            )

        db.commit()

    try:

        yield first_user_id, second_user_id

    finally:

        with SessionLocal() as db:

            db.execute(
                text("""
                    DELETE FROM dbo.research_job_questions
                    WHERE research_job_id IN (
                        SELECT id
                        FROM dbo.research_jobs
                        WHERE user_id IN (
                            :first_user_id,
                            :second_user_id
                        )
                    )
                """),
                {
                    "first_user_id": first_user_id,
                    "second_user_id": second_user_id,
                },
            )

            db.execute(
                text("""
                    DELETE FROM dbo.research_jobs
                    WHERE user_id IN (
                        :first_user_id,
                        :second_user_id
                    )
                """),
                {
                    "first_user_id": first_user_id,
                    "second_user_id": second_user_id,
                },
            )

            db.execute(
                text("""
                    DELETE FROM dbo.users
                    WHERE id IN (
                        :first_user_id,
                        :second_user_id
                    )
                """),
                {
                    "first_user_id": first_user_id,
                    "second_user_id": second_user_id,
                },
            )

            db.commit()


def create_test_draft(
    user_id: str,
    topic: str = "Initial research topic",
    scope: str | None = "Initial scope",
) -> str:

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        return repository.create_draft(
            user_id=user_id,
            topic=topic,
            scope=scope,
        )


def load_job(
    job_id: str,
) -> ResearchJob:

    with SessionLocal() as db:

        job = db.get(
            ResearchJob,
            job_id,
        )

        assert job is not None

        db.expunge(job)

        return job


def test_create_draft(test_users):

    user_id, _ = test_users

    job_id = create_test_draft(
        user_id=user_id,
    )

    job = load_job(job_id)

    assert job.user_id == user_id
    assert job.status == "draft"
    assert job.topic == "Initial research topic"
    assert job.scope == "Initial scope"

    assert job.created_at is not None
    assert job.submitted_at is None
    assert job.started_at is None
    assert job.research_session_id is None
    assert job.execution_owner is None
    assert job.lease_version == 0


def test_update_draft(test_users):

    user_id, _ = test_users

    job_id = create_test_draft(user_id)

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        updated = repository.update_draft(
            job_id=job_id,
            user_id=user_id,
            topic="Updated research topic",
            scope="Updated research scope",
        )

    assert updated is True

    job = load_job(job_id)

    assert job.status == "draft"
    assert job.topic == "Updated research topic"
    assert job.scope == "Updated research scope"


def test_update_draft_can_clear_scope(test_users):

    user_id, _ = test_users

    job_id = create_test_draft(user_id)

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        updated = repository.update_draft(
            job_id=job_id,
            user_id=user_id,
            topic="Updated topic",
            scope=None,
        )

    assert updated is True

    job = load_job(job_id)

    assert job.scope is None


def test_submit_draft(test_users):

    user_id, _ = test_users

    job_id = create_test_draft(user_id)

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        submitted = repository.submit_draft(
            job_id=job_id,
            user_id=user_id,
        )

    assert submitted is True

    job = load_job(job_id)

    assert job.status == "queued"
    assert job.submitted_at is not None
    assert job.created_at is not None
    assert job.submitted_at >= job.created_at
    assert job.research_session_id is None


def test_submitted_draft_cannot_be_modified(test_users):

    user_id, _ = test_users

    job_id = create_test_draft(user_id)

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        assert repository.submit_draft(
            job_id=job_id,
            user_id=user_id,
        )

        updated = repository.update_draft(
            job_id=job_id,
            user_id=user_id,
            topic="Forbidden modification",
            scope="Forbidden scope",
        )

    assert updated is False

    job = load_job(job_id)

    assert job.status == "queued"
    assert job.topic == "Initial research topic"
    assert job.scope == "Initial scope"


def test_submit_draft_twice(test_users):

    user_id, _ = test_users

    job_id = create_test_draft(user_id)

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        first_result = repository.submit_draft(
            job_id=job_id,
            user_id=user_id,
        )

        first_job = load_job(job_id)
        first_submitted_at = first_job.submitted_at

        second_result = repository.submit_draft(
            job_id=job_id,
            user_id=user_id,
        )

    assert first_result is True
    assert second_result is False

    job = load_job(job_id)

    assert job.status == "queued"
    assert job.submitted_at == first_submitted_at


def test_other_user_cannot_modify_or_submit(
    test_users,
):

    owner_id, other_user_id = test_users

    job_id = create_test_draft(owner_id)

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        updated = repository.update_draft(
            job_id=job_id,
            user_id=other_user_id,
            topic="Unauthorized topic",
            scope="Unauthorized scope",
        )

        submitted = repository.submit_draft(
            job_id=job_id,
            user_id=other_user_id,
        )

    assert updated is False
    assert submitted is False

    job = load_job(job_id)

    assert job.status == "draft"
    assert job.topic == "Initial research topic"
    assert job.scope == "Initial scope"


def test_draft_is_not_claimable(test_users):

    user_id, _ = test_users

    job_id = create_test_draft(user_id)

    with SessionLocal() as db:

        eligible_jobs = db.execute(
            text("""
                SELECT COUNT(*)
                FROM dbo.research_jobs
                WHERE status = 'queued'
                   OR (
                       status = 'claimed'
                       AND lease_expires_at <= SYSUTCDATETIME()
                   )
            """)
        ).scalar_one()

    if eligible_jobs != 0:

        pytest.skip(
            "Shared database contains other claimable jobs."
        )

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        claimed = repository.claim_next(
            duration_seconds=120,
        )

    assert claimed is None

    job = load_job(job_id)

    assert job.status == "draft"
    assert job.execution_owner is None


def test_submission_respects_database_row_lock(
    test_users,
):

    user_id, _ = test_users

    job_id = create_test_draft(user_id)

    lock_acquired = Event()
    release_lock = Event()

    def hold_job_lock():

        with SessionLocal() as db:

            try:

                db.execute(
                    text("""
                        SELECT id
                        FROM dbo.research_jobs
                            WITH (UPDLOCK, HOLDLOCK)
                        WHERE id = :job_id
                    """),
                    {
                        "job_id": job_id,
                    },
                ).scalar_one()

                lock_acquired.set()

                if not release_lock.wait(timeout=15):

                    raise RuntimeError(
                        "Timed out waiting to release "
                        "the job lock."
                    )

                db.commit()

            except Exception:

                db.rollback()
                raise

    with ThreadPoolExecutor(
        max_workers=1
    ) as executor:

        future = executor.submit(
            hold_job_lock
        )

        try:

            assert lock_acquired.wait(timeout=10)

            with SessionLocal() as db:

                db.execute(
                    text("SET LOCK_TIMEOUT 1000")
                )

                try:

                    with pytest.raises(DBAPIError):

                        ResearchJobRepository(
                            db
                        ).submit_draft(
                            job_id=job_id,
                            user_id=user_id,
                        )

                finally:

                    db.rollback()

        finally:

            release_lock.set()

        future.result(timeout=15)

    job = load_job(job_id)

    assert job.status == "draft"
    assert job.submitted_at is None

    with SessionLocal() as db:

        submitted = ResearchJobRepository(
            db
        ).submit_draft(
            job_id=job_id,
            user_id=user_id,
        )

    assert submitted is True

    job = load_job(job_id)

    assert job.status == "queued"


def test_add_draft_question(test_users):

    user_id, _ = test_users

    job_id = create_test_draft(user_id)

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        question_id = repository.add_draft_question(
            job_id=job_id,
            user_id=user_id,
            question="What are the principal risks?",
        )

        questions = repository.list_draft_questions(
            job_id=job_id,
            user_id=user_id,
        )

    assert question_id is not None
    assert len(questions) == 1

    assert questions[0].id == question_id
    assert questions[0].research_job_id == job_id
    assert questions[0].question == (
        "What are the principal risks?"
    )
    assert questions[0].created_at is not None


def test_multiple_draft_questions(test_users):

    user_id, _ = test_users

    job_id = create_test_draft(user_id)

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        first_id = repository.add_draft_question(
            job_id=job_id,
            user_id=user_id,
            question="What is the current situation?",
        )

        second_id = repository.add_draft_question(
            job_id=job_id,
            user_id=user_id,
            question="What might change in the future?",
        )

        questions = repository.list_draft_questions(
            job_id=job_id,
            user_id=user_id,
        )

    assert first_id is not None
    assert second_id is not None
    assert first_id != second_id

    assert len(questions) == 2

    assert [item.id for item in questions] == [
        first_id,
        second_id,
    ]


def test_remove_draft_question(test_users):

    user_id, _ = test_users

    job_id = create_test_draft(user_id)

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        question_id = repository.add_draft_question(
            job_id=job_id,
            user_id=user_id,
            question="Question to remove",
        )

        assert question_id is not None

        removed = repository.remove_draft_question(
            job_id=job_id,
            user_id=user_id,
            question_id=question_id,
        )

        questions = repository.list_draft_questions(
            job_id=job_id,
            user_id=user_id,
        )

    assert removed is True
    assert questions == []


def test_submitted_questions_are_immutable(
    test_users,
):

    user_id, _ = test_users

    job_id = create_test_draft(user_id)

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        question_id = repository.add_draft_question(
            job_id=job_id,
            user_id=user_id,
            question="Original question",
        )

        assert question_id is not None

        submitted = repository.submit_draft(
            job_id=job_id,
            user_id=user_id,
        )

        added_id = repository.add_draft_question(
            job_id=job_id,
            user_id=user_id,
            question="Question added too late",
        )

        removed = repository.remove_draft_question(
            job_id=job_id,
            user_id=user_id,
            question_id=question_id,
        )

        questions = repository.list_draft_questions(
            job_id=job_id,
            user_id=user_id,
        )

    assert submitted is True
    assert added_id is None
    assert removed is False

    assert len(questions) == 1
    assert questions[0].question == "Original question"


def test_other_user_cannot_access_draft_questions(
    test_users,
):

    owner_id, other_user_id = test_users

    job_id = create_test_draft(owner_id)

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        question_id = repository.add_draft_question(
            job_id=job_id,
            user_id=owner_id,
            question="Private research question",
        )

        assert question_id is not None

        unauthorized_add = repository.add_draft_question(
            job_id=job_id,
            user_id=other_user_id,
            question="Unauthorized question",
        )

        unauthorized_remove = (
            repository.remove_draft_question(
                job_id=job_id,
                user_id=other_user_id,
                question_id=question_id,
            )
        )

        unauthorized_list = (
            repository.list_draft_questions(
                job_id=job_id,
                user_id=other_user_id,
            )
        )

        owner_list = repository.list_draft_questions(
            job_id=job_id,
            user_id=owner_id,
        )

    assert unauthorized_add is None
    assert unauthorized_remove is False
    assert unauthorized_list == []

    assert len(owner_list) == 1
    assert owner_list[0].id == question_id


def test_question_add_respects_job_row_lock(
    test_users,
):

    user_id, _ = test_users

    job_id = create_test_draft(user_id)

    lock_acquired = Event()
    release_lock = Event()

    def hold_job_lock():

        with SessionLocal() as db:

            try:

                db.execute(
                    text("""
                        SELECT id
                        FROM dbo.research_jobs
                            WITH (UPDLOCK, HOLDLOCK)
                        WHERE id = :job_id
                    """),
                    {
                        "job_id": job_id,
                    },
                ).scalar_one()

                connection_info = db.execute(
                    text("""
                        SELECT
                            @@SPID AS session_id,
                            @@TRANCOUNT AS transaction_count,
                            DB_NAME() AS database_name,
                            @@OPTIONS AS session_options
                    """)
                ).one()

                print(
                    "\nLock holder connection:",
                    connection_info,
                    flush=True,
                )

                lock_acquired.set()

                if not release_lock.wait(timeout=15):

                    raise RuntimeError(
                        "Timed out waiting to release "
                        "the draft job lock."
                    )

                db.commit()

            except Exception:

                db.rollback()
                raise

    with ThreadPoolExecutor(
        max_workers=1
    ) as executor:

        future = executor.submit(
            hold_job_lock
        )

        try:

            if not lock_acquired.wait(timeout=10):

                if future.done():

                    future.result()

                pytest.fail(
                    "Lock-holder thread did not signal "
                    "that the job lock was acquired."
                )

            with SessionLocal() as db:

                try:

                    db.execute(
                        text("SET LOCK_TIMEOUT 1000")
                    )

                    connection_info = db.execute(
                        text("""
                            SELECT
                                @@SPID AS session_id,
                                @@TRANCOUNT AS transaction_count,
                                DB_NAME() AS database_name,
                                @@OPTIONS AS session_options
                        """)
                    ).one()

                    print(
                        "\nQuestion writer connection:",
                        connection_info,
                        flush=True,
                    )

                    # Diagnostic: request the same update lock
                    # from an independent SQL Server session.
                    with pytest.raises(DBAPIError):

                        db.execute(
                            text("""
                                SELECT id
                                FROM dbo.research_jobs
                                    WITH (UPDLOCK, HOLDLOCK)
                                WHERE id = :job_id
                            """),
                            {
                                "job_id": job_id,
                            },
                        ).scalar_one()

                finally:

                    db.rollback()

                    # LOCK_TIMEOUT is a connection-level setting;
                    # restore the default before pooling the connection.
                    db.execute(
                        text("SET LOCK_TIMEOUT -1")
                    )
                    db.commit()

        finally:

            release_lock.set()

        future.result(timeout=15)

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        questions = repository.list_draft_questions(
            job_id=job_id,
            user_id=user_id,
        )

    assert questions == []
