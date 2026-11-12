from datetime import datetime

from sqlalchemy import text

from persistence.database import SessionLocal

from persistence.research_job_repository import (
    ResearchJobRepository,
)


def get_test_user_id() -> str:

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
            "No existing user is available for the test."
        )

    return user_id


def main() -> None:

    user_id = get_test_user_id()

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic="Abandoned pause reconciliation test",
        )

    print(
        f"Created job: {job_id}"
    )

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        claimed = repository.claim_next(
            duration_seconds=120,
        )

    assert claimed is not None

    assert claimed.job_id == job_id, (
        "A different queued job was claimed. "
        "Stop the test and inspect the job queue."
    )

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        session_id = repository.associate_session(
            claimed.lease
        )

    print(
        f"Associated session: {session_id}"
    )

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        pause_result = repository.request_pause(
            job_id=job_id,
            user_id=user_id,
        )

    assert pause_result == "pause_requested"

    print(
        "Pause request persisted."
    )

    with SessionLocal() as db:

        statement = text("""
            UPDATE dbo.research_jobs
            SET lease_expires_at = DATEADD(
                second,
                -1,
                SYSUTCDATETIME()
            )
            WHERE id = :job_id
              AND status = 'claimed'
        """)

        db.execute(
            statement,
            {
                "job_id": job_id,
            },
        )

        db.commit()

    print(
        "Simulated expired worker lease."
    )

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        reconciled_count = (
            repository.reconcile_abandoned_pauses(
                limit=100,
            )
        )

    print(
        f"Reconciled jobs: {reconciled_count}"
    )

    assert reconciled_count >= 1

    with SessionLocal() as db:

        statement = text("""
            SELECT
                j.status,
                j.research_session_id,
                j.execution_owner,
                j.lease_expires_at,
                s.pause_requested,
                s.status
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

    assert result[0] == "paused"
    assert result[1] == session_id
    assert result[2] is None
    assert result[3] is None
    assert result[4] in (True, 1)
    assert result[5] != "completed"

    print(
        "Abandoned pause reconciliation: PASSED"
    )

    print(
        f"Job ID: {job_id}"
    )

    print(
        f"Session ID: {session_id}"
    )


if __name__ == "__main__":

    main()