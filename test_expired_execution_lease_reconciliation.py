from sqlalchemy import text

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
)

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

    return str(user_id)


def main() -> None:

    user_id = get_test_user_id()

    with SessionLocal() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.submit(
            user_id=user_id,
            topic="Expired execution lease reconciliation test",
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
        "Inspect the job queue before continuing."
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

        repository = ExecutionLeaseRepository(db)

        execution_lease = repository.acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    print(
        "Session execution lease acquired."
    )

    print(
        f"Execution lease version: {execution_lease.version}"
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
              AND execution_owner = :job_owner
              AND lease_version = :job_version
        """)

        result = db.execute(
            statement,
            {
                "job_id": job_id,
                "job_owner": claimed.lease.owner,
                "job_version": claimed.lease.version,
            },
        )

        assert result.rowcount == 1

        statement = text("""
            UPDATE dbo.research_sessions
            SET execution_lease_expires_at = DATEADD(
                second,
                -1,
                SYSUTCDATETIME()
            )
            WHERE id = :session_id
              AND execution_owner = :execution_owner
              AND execution_lease_version = :execution_version
        """)

        result = db.execute(
            statement,
            {
                "session_id": session_id,
                "execution_owner": execution_lease.owner,
                "execution_version": execution_lease.version,
            },
        )

        assert result.rowcount == 1

        db.commit()

    print(
        "Simulated expiration of both leases."
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
                j.status AS job_status,
                j.research_session_id,
                j.execution_owner AS job_owner,
                j.lease_expires_at AS job_lease_expiry,
                j.lease_version AS job_lease_version,
                s.status AS session_status,
                s.pause_requested,
                s.execution_owner AS session_owner,
                s.execution_lease_expires_at
                    AS session_lease_expiry,
                s.execution_lease_version
                    AS session_lease_version
            FROM dbo.research_jobs AS j
            INNER JOIN dbo.research_sessions AS s
                ON s.id = j.research_session_id
            WHERE j.id = :job_id
        """)

        row = db.execute(
            statement,
            {
                "job_id": job_id,
            },
        ).mappings().one()

    assert row["job_status"] == "paused"

    assert str(row["research_session_id"]) == session_id

    assert row["job_owner"] is None

    assert row["job_lease_expiry"] is None

    assert row["job_lease_version"] == (
        claimed.lease.version + 1
    )

    assert row["session_status"] != "completed"

    assert row["pause_requested"] in (True, 1)

    assert row["session_owner"] == execution_lease.owner

    assert row["session_lease_expiry"] is not None

    assert row["session_lease_version"] == (
        execution_lease.version
    )

    print(
        "Expired execution lease reconciliation: PASSED"
    )

    print(
        f"Job ID: {job_id}"
    )

    print(
        f"Session ID: {session_id}"
    )


if __name__ == "__main__":

    main()