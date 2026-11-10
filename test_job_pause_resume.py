from persistence.database import SessionLocal
from persistence.research_job_repository import (
    ResearchJobRepository,
)

from sqlalchemy import text


def main() -> None:

    with SessionLocal() as db:

        statement = text("""
            SELECT TOP (1)
                id
            FROM dbo.users
            ORDER BY id
        """)

        user_id = db.execute(
            statement
        ).scalar_one_or_none()

    if user_id is None:

        raise RuntimeError(
            "No existing users found in dbo.users. "
            "Create a test user before running this test."
        )

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic="Pause and resume integration test",
        )

    print(f"Created job: {job_id}")

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        result = repository.request_pause(
            job_id=job_id,
            user_id=user_id,
        )

    print(f"Pause result: {result}")

    assert result == "paused"

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        job = db.execute(
            text("""
                SELECT
                    status,
                    research_session_id,
                    execution_owner,
                    lease_expires_at
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job_id,
            },
        ).first()

    assert job is not None
    assert job[0] == "paused"
    assert job[1] is None
    assert job[2] is None
    assert job[3] is None

    print("Queued job pause: PASSED")

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        resumed = repository.resume_paused(
            job_id=job_id,
            user_id=user_id,
        )

    assert resumed is True

    with SessionLocal() as db:

        job = db.execute(
            text("""
                SELECT
                    status
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job_id,
            },
        ).first()

    assert job is not None
    assert job[0] == "queued"

    print("Queued job resume: PASSED")


if __name__ == "__main__":

    main()