from sqlalchemy import text

from persistence.database import SessionLocal

from persistence.research_job_repository import (
    ResearchJobRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


def main() -> None:

    job_id = (
        "3e2779bb-3882-41a6-9569-f105a6fe6389"
    )

    session_id = (
        "461fa596-87d1-452b-b4ab-86d774c4dd9d"
    )

    with SessionLocal() as db:

        repository = ResearchSessionRepository(db)

        candidates = repository.find_recovery_candidates(
            limit=1000,
        )

    assert session_id not in candidates

    print(
        "Paused session excluded from recovery: PASSED"
    )

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        reconciled_count = (
            repository.reconcile_abandoned_pauses(
                limit=100,
            )
        )

    assert reconciled_count == 0, (
        "Unexpected abandoned jobs were reconciled. "
        "Inspect the database before continuing."
    )

    print(
        "Reconciliation idempotency: PASSED"
    )

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

    assert result[0] == "paused"

    assert result[1] == session_id

    assert result[2] in (True, 1)

    print(
        "Paused job state preserved: PASSED"
    )


if __name__ == "__main__":

    main()