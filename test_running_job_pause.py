from sqlalchemy import text

from persistence.database import SessionLocal

from persistence.research_job_repository import (
    ResearchJobRepository,
)


def main() -> None:

    job_id = input(
        "Enter the running job ID: "
    ).strip()

    if not job_id:

        raise ValueError(
            "A job ID is required."
        )

    with SessionLocal() as db:

        statement = text("""
            SELECT
                user_id
            FROM dbo.research_jobs
            WHERE id = :job_id
        """)

        user_id = db.execute(
            statement,
            {
                "job_id": job_id,
            },
        ).scalar_one_or_none()

    if user_id is None:

        raise ValueError(
            f"Research job not found: {job_id}"
        )

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        result = repository.request_pause(
            job_id=job_id,
            user_id=user_id,
        )

    print(
        f"Pause request result: {result}"
    )

    assert result == "pause_requested"

    print(
        "Running job pause request: PASSED"
    )


if __name__ == "__main__":

    main()