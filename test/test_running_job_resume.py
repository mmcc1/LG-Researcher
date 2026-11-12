from sqlalchemy import text

from persistence.database import SessionLocal

from persistence.research_job_repository import (
    ResearchJobRepository,
)


def main() -> None:

    job_id = (
        "ebdcabed-ac70-4c83-a4ef-c9c30517e385"
    )

    expected_session_id = (
        "fae64b4b-4400-43a2-a3d0-4fd3ac76641c"
    )

    with SessionLocal() as db:

        statement = text("""
            SELECT
                user_id,
                status,
                research_session_id
            FROM dbo.research_jobs
            WHERE id = :job_id
        """)

        job = db.execute(
            statement,
            {
                "job_id": job_id,
            },
        ).first()

    if job is None:

        raise RuntimeError(
            f"Research job not found: {job_id}"
        )

    user_id = job[0]
    status = job[1]
    session_id = job[2]

    assert status == "paused"

    assert session_id == expected_session_id

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        resumed = repository.resume_paused(
            job_id=job_id,
            user_id=user_id,
        )

    assert resumed is True

    with SessionLocal() as db:

        statement = text("""
            SELECT
                j.status,
                j.research_session_id,
                s.pause_requested
            FROM dbo.research_jobs AS j
            INNER JOIN dbo.research_sessions AS s
                ON s.id = j.research_session_id
            WHERE j.id = :job_id
        """)

        result = db.execute(
            statement,
            {
                "job_id": job_id,
            },
        ).first()

    assert result is not None

    assert result[0] == "queued"

    assert result[1] == expected_session_id

    assert result[2] in (False, 0)

    print(
        "Running job resume: PASSED"
    )

    print(
        f"Job ID: {job_id}"
    )

    print(
        f"Session ID: {expected_session_id}"
    )

    print(
        "Job returned to queue with its "
        "original research session."
    )


if __name__ == "__main__":

    main()