
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from persistence.database import engine
from persistence.models import UserAccount
from persistence.research_job_repository import (
    ResearchJobRepository,
)

from persistence.research_job_repository import (
    ResearchJobLeaseUnavailable,
)

from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from persistence.models import ResearchSession


TEST_DATABASE = "LGResearcher_Test"


@pytest.fixture
def test_environment():

    test_url = engine.url.set(
        database=TEST_DATABASE
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

    user_id = str(uuid4())

    now = datetime.now(timezone.utc).replace(
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

            db.execute(
                text("""
                    DELETE q
                    FROM dbo.research_job_questions AS q
                    INNER JOIN dbo.research_jobs AS j
                        ON j.id = q.research_job_id
                    WHERE j.user_id = :user_id
                """),
                {
                    "user_id": user_id,
                },
            )

            db.execute(
                text("""
                    DELETE FROM dbo.research_jobs
                    WHERE user_id = :user_id
                """),
                {
                    "user_id": user_id,
                },
            )

            db.execute(
                text("""
                    DELETE FROM dbo.users
                    WHERE id = :user_id
                """),
                {
                    "user_id": user_id,
                },
            )

            db.commit()

        test_engine.dispose()



def test_sql_submit_and_claim(test_environment):

    Session, user_id = test_environment

    with Session() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic="SQL integration research",
            scope="Test scope",
        )

        claimed = repository.claim_next()

        assert claimed is not None
        assert claimed.job_id == job_id
        assert claimed.user_id == user_id
        assert claimed.topic == "SQL integration research"
        assert claimed.scope == "Test scope"
        assert claimed.lease.version == 1

        stored = db.execute(
            text("""
                SELECT
                    status,
                    execution_owner,
                    lease_version
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {"job_id": job_id},
        ).one()

        assert stored[0] == "claimed"
        assert stored[1] == claimed.lease.owner
        assert stored[2] == 1


def test_sql_claim_order(test_environment):

    Session, user_id = test_environment

    with Session() as db:

        repository = ResearchJobRepository(db)

        first_id = repository.submit(
            user_id=user_id,
            topic="First job",
        )

        second_id = repository.submit(
            user_id=user_id,
            topic="Second job",
        )

        first_claim = repository.claim_next()
        second_claim = repository.claim_next()

        assert first_claim is not None
        assert second_claim is not None

        assert first_claim.job_id == first_id
        assert second_claim.job_id == second_id


def test_sql_concurrent_claims(test_environment):

    Session, user_id = test_environment

    with Session() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic="Concurrent claim test",
        )

    def attempt_claim():

        with Session() as db:

            repository = ResearchJobRepository(db)

            return repository.claim_next()

    with ThreadPoolExecutor(max_workers=2) as executor:

        futures = [
            executor.submit(attempt_claim)
            for _ in range(2)
        ]

        results = [
            future.result()
            for future in futures
        ]

    successful = [
        result
        for result in results
        if result is not None
    ]

    assert len(successful) == 1
    assert successful[0].job_id == job_id


def test_sql_renew_and_stale_lease(test_environment):

    Session, user_id = test_environment

    with Session() as db:

        repository = ResearchJobRepository(db)

        repository.submit(
            user_id=user_id,
            topic="Lease renewal test",
        )

        claimed = repository.claim_next()

        assert claimed is not None

        renewed = repository.renew(
            claimed.lease,
            duration_seconds=300,
        )

        assert renewed is not None
        assert renewed.version == claimed.lease.version

        released = repository.release(
            renewed
        )

        assert released is True

        stale_renewal = repository.renew(
            claimed.lease
        )

        assert stale_renewal is None


def test_sql_expired_claim_recovery(test_environment):

    Session, user_id = test_environment

    with Session() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic="Expired claim test",
        )

        original = repository.claim_next()

        assert original is not None

        db.execute(
            text("""
                UPDATE dbo.research_jobs
                SET lease_expires_at =
                    DATEADD(
                        second,
                        -10,
                        SYSUTCDATETIME()
                    )
                WHERE id = :job_id
            """),
            {"job_id": job_id},
        )

        db.commit()

        recovered = repository.claim_next()

        assert recovered is not None
        assert recovered.job_id == job_id

        assert (
            recovered.lease.version
            > original.lease.version
        )

        assert (
            recovered.lease.owner
            != original.lease.owner
        )

        assert repository.renew(
            original.lease
        ) is None

        assert repository.release(
            original.lease
        ) is False


def test_sql_release_returns_job_to_queue(
    test_environment,
):

    Session, user_id = test_environment

    with Session() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic="Release test",
        )

        original = repository.claim_next()

        assert original is not None

        assert repository.release(
            original.lease
        ) is True

        reclaimed = repository.claim_next()

        assert reclaimed is not None
        assert reclaimed.job_id == job_id

        assert (
            reclaimed.lease.version
            > original.lease.version
        )



def test_sql_associate_session(test_environment):

    Session, user_id = test_environment

    session_id = None

    try:

        with Session() as db:

            repository = ResearchJobRepository(db)

            job_id = repository.submit(
                user_id=user_id,
                topic="Atomic association test",
                scope="Test scope",
            )

            claimed = repository.claim_next()

            assert claimed is not None

            session_id = repository.associate_session(
                claimed.lease
            )

            row = db.execute(
                text("""
                    SELECT
                        j.research_session_id,
                        s.topic,
                        s.scope,
                        s.status
                    FROM dbo.research_jobs AS j
                    INNER JOIN dbo.research_sessions AS s
                        ON s.id = j.research_session_id
                    WHERE j.id = :job_id
                """),
                {"job_id": job_id},
            ).one()

            assert row[0] == session_id
            assert row[1] == "Atomic association test"
            assert row[2] == "Test scope"
            assert row[3] == "created"

    finally:

        if session_id is not None:

            with Session() as db:

                db.execute(
                    text("""
                        UPDATE dbo.research_jobs
                        SET research_session_id = NULL
                        WHERE research_session_id = :session_id
                    """),
                    {"session_id": session_id},
                )

                db.execute(
                    text("""
                        DELETE FROM dbo.research_sessions
                        WHERE id = :session_id
                    """),
                    {"session_id": session_id},
                )

                db.commit()


def test_sql_association_is_idempotent(
    test_environment,
):

    Session, user_id = test_environment

    session_id = None

    try:

        with Session() as db:

            repository = ResearchJobRepository(db)

            repository.submit(
                user_id=user_id,
                topic="Idempotent association test",
            )

            claimed = repository.claim_next()

            assert claimed is not None

            session_id = repository.associate_session(
                claimed.lease
            )

            repeated_session_id = (
                repository.associate_session(
                    claimed.lease
                )
            )

            assert repeated_session_id == session_id

            count = db.execute(
                text("""
                    SELECT COUNT(*)
                    FROM dbo.research_sessions
                    WHERE id = :session_id
                """),
                {"session_id": session_id},
            ).scalar_one()

            assert count == 1

    finally:

        if session_id is not None:

            with Session() as db:

                db.execute(
                    text("""
                        UPDATE dbo.research_jobs
                        SET research_session_id = NULL
                        WHERE research_session_id = :session_id
                    """),
                    {"session_id": session_id},
                )

                db.execute(
                    text("""
                        DELETE FROM dbo.research_sessions
                        WHERE id = :session_id
                    """),
                    {"session_id": session_id},
                )

                db.commit()


def test_sql_stale_lease_cannot_associate(
    test_environment,
):

    Session, user_id = test_environment

    with Session() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic="Stale association test",
        )

        claimed = repository.claim_next()

        assert claimed is not None

        assert repository.release(
            claimed.lease
        ) is True

        with pytest.raises(
            ResearchJobLeaseUnavailable
        ):

            repository.associate_session(
                claimed.lease
            )

        row = db.execute(
            text("""
                SELECT research_session_id
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {"job_id": job_id},
        ).one()

        assert row[0] is None



def test_sql_association_rollback(
    test_environment,
):

    Session, user_id = test_environment

    with Session() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic="Association rollback test",
        )

        claimed = repository.claim_next()

        assert claimed is not None

        original_execute = db.execute

        def failing_execute(
            statement,
            *args,
            **kwargs,
        ):

            statement_text = str(statement)

            if (
                "UPDATE dbo.research_jobs" in statement_text
                and "research_session_id = :session_id"
                in statement_text
            ):

                raise SQLAlchemyError(
                    "Simulated association update failure."
                )

            return original_execute(
                statement,
                *args,
                **kwargs,
            )

        with patch.object(
            db,
            "execute",
            side_effect=failing_execute,
        ):

            with pytest.raises(
                SQLAlchemyError,
                match="Simulated association update failure",
            ):

                repository.associate_session(
                    claimed.lease
                )

    with Session() as db:

        row = db.execute(
            text("""
                SELECT research_session_id
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {"job_id": job_id},
        ).one()

        assert row[0] is None

        count = db.execute(
            text("""
                SELECT COUNT(*)
                FROM dbo.research_sessions
                WHERE topic = :topic
            """),
            {
                "topic": "Association rollback test",
            },
        ).scalar_one()

        assert count == 0



def test_sql_concurrent_association(
    test_environment,
):

    Session, user_id = test_environment

    session_id = None

    try:

        with Session() as db:

            repository = ResearchJobRepository(db)

            job_id = repository.submit(
                user_id=user_id,
                topic="Concurrent association test",
            )

            claimed = repository.claim_next()

            assert claimed is not None

            lease = claimed.lease

        def associate():

            with Session() as db:

                repository = ResearchJobRepository(db)

                return repository.associate_session(
                    lease
                )

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:

            futures = [
                executor.submit(associate)
                for _ in range(2)
            ]

            results = [
                future.result()
                for future in futures
            ]

        assert results[0] == results[1]

        session_id = results[0]

        with Session() as db:

            row = db.execute(
                text("""
                    SELECT research_session_id
                    FROM dbo.research_jobs
                    WHERE id = :job_id
                """),
                {"job_id": job_id},
            ).one()

            assert row[0] == session_id

            count = db.execute(
                text("""
                    SELECT COUNT(*)
                    FROM dbo.research_sessions
                    WHERE topic = :topic
                """),
                {
                    "topic": "Concurrent association test",
                },
            ).scalar_one()

            assert count == 1

    finally:

        if session_id is not None:

            with Session() as db:

                db.execute(
                    text("""
                        UPDATE dbo.research_jobs
                        SET research_session_id = NULL
                        WHERE research_session_id = :session_id
                    """),
                    {"session_id": session_id},
                )

                db.execute(
                    text("""
                        DELETE FROM dbo.research_sessions
                        WHERE id = :session_id
                    """),
                    {"session_id": session_id},
                )

                db.commit()



def test_sql_reclaim_associated_job(
    test_environment,
):

    Session, user_id = test_environment

    session_id = None

    try:

        with Session() as db:

            repository = ResearchJobRepository(db)

            job_id = repository.submit(
                user_id=user_id,
                topic="Associated job recovery test",
            )

            original_claim = repository.claim_next()

            assert original_claim is not None

            session_id = repository.associate_session(
                original_claim.lease
            )

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

            recovered_claim = repository.claim_next()

            assert recovered_claim is not None

            assert recovered_claim.job_id == job_id

            assert (
                recovered_claim.research_session_id
                == session_id
            )

            assert (
                recovered_claim.lease.owner
                != original_claim.lease.owner
            )

            assert (
                recovered_claim.lease.version
                > original_claim.lease.version
            )

            assert repository.renew(
                original_claim.lease
            ) is None

            assert repository.release(
                original_claim.lease
            ) is False

    finally:

        if session_id is not None:

            with Session() as db:

                db.execute(
                    text("""
                        UPDATE dbo.research_jobs
                        SET research_session_id = NULL
                        WHERE research_session_id = :session_id
                    """),
                    {
                        "session_id": session_id,
                    },
                )

                db.execute(
                    text("""
                        DELETE FROM dbo.research_sessions
                        WHERE id = :session_id
                    """),
                    {
                        "session_id": session_id,
                    },
                )

                db.commit()




def test_sql_concurrent_associated_job_recovery(
    test_environment,
):

    Session, user_id = test_environment

    session_id = None

    try:

        with Session() as db:

            repository = ResearchJobRepository(db)

            job_id = repository.submit(
                user_id=user_id,
                topic="Concurrent associated recovery test",
            )

            original_claim = repository.claim_next()

            assert original_claim is not None

            session_id = repository.associate_session(
                original_claim.lease
            )

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

        def recover_job():

            with Session() as db:

                repository = ResearchJobRepository(db)

                return repository.claim_next()

        with ThreadPoolExecutor(
            max_workers=2
        ) as executor:

            futures = [
                executor.submit(recover_job)
                for _ in range(2)
            ]

            results = [
                future.result()
                for future in futures
            ]

        successful_claims = [
            result
            for result in results
            if result is not None
        ]

        assert len(successful_claims) == 1

        recovered_claim = successful_claims[0]

        assert recovered_claim.job_id == job_id

        assert (
            recovered_claim.research_session_id
            == session_id
        )

        assert (
            recovered_claim.lease.version
            > original_claim.lease.version
        )

    finally:

        if session_id is not None:

            with Session() as db:

                db.execute(
                    text("""
                        UPDATE dbo.research_jobs
                        SET research_session_id = NULL
                        WHERE research_session_id = :session_id
                    """),
                    {
                        "session_id": session_id,
                    },
                )

                db.execute(
                    text("""
                        DELETE FROM dbo.research_sessions
                        WHERE id = :session_id
                    """),
                    {
                        "session_id": session_id,
                    },
                )

                db.commit()



def test_sql_submitted_questions_available_to_session(
    test_environment,
):

    Session, user_id = test_environment

    session_id = None

    original_questions = [
        "How does Shor's algorithm threaten Bitcoin?",
        "What post-quantum signatures could Bitcoin adopt?",
    ]

    try:

        with Session() as db:

            repository = ResearchJobRepository(db)

            job_id = repository.create_draft(
                user_id=user_id,
                topic="Quantum computing and Bitcoin",
                scope="Cryptographic threats and mitigations",
            )

            for question in original_questions:

                question_id = repository.add_draft_question(
                    job_id=job_id,
                    user_id=user_id,
                    question=question,
                )

                assert question_id is not None

            submitted = repository.submit_draft(
                job_id=job_id,
                user_id=user_id,
            )

            assert submitted is True

            claimed = repository.claim_next()

            assert claimed is not None
            assert claimed.job_id == job_id

            session_id = repository.associate_session(
                claimed.lease
            )

            retrieved_questions = (
                repository.list_session_job_questions(
                    session_id=session_id,
                )
            )

            assert retrieved_questions == original_questions

            repeated_questions = (
                repository.list_session_job_questions(
                    session_id=session_id,
                )
            )

            assert repeated_questions == original_questions

    finally:

        if session_id is not None:

            with Session() as db:

                db.execute(
                    text("""
                        UPDATE dbo.research_jobs
                        SET research_session_id = NULL
                        WHERE research_session_id = :session_id
                    """),
                    {
                        "session_id": session_id,
                    },
                )

                db.execute(
                    text("""
                        DELETE FROM dbo.research_sessions
                        WHERE id = :session_id
                    """),
                    {
                        "session_id": session_id,
                    },
                )

                db.commit()


def cleanup_associated_session(
    Session,
    job_id,
    session_id,
):

    with Session() as db:

        db.execute(
            text("""
                UPDATE dbo.research_jobs
                SET research_session_id = NULL
                WHERE id = :job_id
                  AND research_session_id = :session_id
            """),
            {
                "job_id": job_id,
                "session_id": session_id,
            },
        )

        db.execute(
            text("""
                DELETE FROM dbo.research_sessions
                WHERE id = :session_id
            """),
            {
                "session_id": session_id,
            },
        )

        db.commit()


def test_sql_complete_requires_completed_session(
    test_environment,
):

    Session, user_id = test_environment

    session_id = None
    job_id = None

    try:

        with Session() as db:

            repository = ResearchJobRepository(db)

            job_id = repository.submit(
                user_id=user_id,
                topic="Premature completion protection",
            )

            claimed = repository.claim_next()

            assert claimed is not None
            assert claimed.job_id == job_id

            session_id = repository.associate_session(
                claimed.lease
            )

            assert repository.complete(
                claimed.lease
            ) is False

            row = db.execute(
                text("""
                    SELECT status, execution_owner, lease_version
                    FROM dbo.research_jobs
                    WHERE id = :job_id
                """),
                {
                    "job_id": job_id,
                },
            ).one()

            assert row[0] == "claimed"
            assert row[1] == claimed.lease.owner
            assert row[2] == claimed.lease.version

    finally:

        if session_id is not None:

            cleanup_associated_session(
                Session=Session,
                job_id=job_id,
                session_id=session_id,
            )


def test_sql_complete_finalizes_completed_session(
    test_environment,
):

    Session, user_id = test_environment

    session_id = None
    job_id = None

    try:

        with Session() as db:

            repository = ResearchJobRepository(db)

            job_id = repository.submit(
                user_id=user_id,
                topic="Completed research job",
            )

            claimed = repository.claim_next()

            assert claimed is not None
            assert claimed.job_id == job_id

            session_id = repository.associate_session(
                claimed.lease
            )

            db.execute(
                text("""
                    UPDATE dbo.research_sessions
                    SET status = 'completed',
                        updated_at = SYSUTCDATETIME()
                    WHERE id = :session_id
                """),
                {
                    "session_id": session_id,
                },
            )

            db.commit()

            assert repository.complete(
                claimed.lease
            ) is True

            row = db.execute(
                text("""
                    SELECT status, execution_owner,
                           lease_expires_at, lease_version,
                           completed_at, last_error
                    FROM dbo.research_jobs
                    WHERE id = :job_id
                """),
                {
                    "job_id": job_id,
                },
            ).one()

            assert row[0] == "completed"
            assert row[1] is None
            assert row[2] is None
            assert row[3] > claimed.lease.version
            assert row[4] is not None
            assert row[5] is None

            assert repository.complete(
                claimed.lease
            ) is False

            assert repository.fail(
                claimed.lease,
                error="Stale completion attempt",
            ) is False

            assert repository.renew(
                claimed.lease
            ) is None

            assert repository.claim_next() is None

    finally:

        if session_id is not None:

            cleanup_associated_session(
                Session=Session,
                job_id=job_id,
                session_id=session_id,
            )


def test_sql_fail_finalizes_claimed_job(
    test_environment,
):

    Session, user_id = test_environment

    with Session() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic="Failed research job",
        )

        claimed = repository.claim_next()

        assert claimed is not None
        assert claimed.job_id == job_id

        assert repository.fail(
            lease=claimed.lease,
            error="  Simulated workflow failure.  ",
        ) is True

        row = db.execute(
            text("""
                SELECT status, execution_owner,
                       lease_expires_at, lease_version,
                       last_error
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job_id,
            },
        ).one()

        assert row[0] == "failed"
        assert row[1] is None
        assert row[2] is None
        assert row[3] > claimed.lease.version
        assert row[4] == "Simulated workflow failure."

        assert repository.fail(
            lease=claimed.lease,
            error="Stale failure attempt",
        ) is False

        assert repository.renew(
            claimed.lease
        ) is None

        assert repository.claim_next() is None


def test_sql_reclaimed_job_rejects_stale_finalization(
    test_environment,
):

    Session, user_id = test_environment

    with Session() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic="Stale worker finalization",
        )

        original = repository.claim_next()

        assert original is not None
        assert original.job_id == job_id

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

        recovered = repository.claim_next()

        assert recovered is not None
        assert recovered.job_id == job_id
        assert recovered.lease.version > original.lease.version
        assert recovered.lease.owner != original.lease.owner

        assert repository.complete(
            original.lease
        ) is False

        assert repository.fail(
            lease=original.lease,
            error="Stale worker error",
        ) is False

        row = db.execute(
            text("""
                SELECT status, execution_owner,
                       lease_version, last_error
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job_id,
            },
        ).one()

        assert row[0] == "claimed"
        assert row[1] == recovered.lease.owner
        assert row[2] == recovered.lease.version
        assert row[3] is None
