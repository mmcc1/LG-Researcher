from dataclasses import replace
from datetime import datetime, timedelta
from time import sleep
from uuid import uuid4

from sqlalchemy import text

from persistence.database import SessionLocal
from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseUnavailable,
)
from persistence.research_session_repository import (
    ResearchSessionRepository,
)


def create_test_session() -> str:

    with SessionLocal() as db:

        repository = ResearchSessionRepository(db)

        session = repository.create(
            topic="Stage 7.21D1 lease renewal test",
            scope="Disposable integration test",
        )

        return session.id


def delete_test_session(session_id: str) -> None:

    with SessionLocal() as db:

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


def acquire_lease(
    session_id: str,
    duration_seconds: int = 120,
):

    with SessionLocal() as db:

        return ExecutionLeaseRepository(db).acquire(
            session_id,
            duration_seconds=duration_seconds,
        )


def renew_lease(
    lease,
    duration_seconds: int = 120,
):

    with SessionLocal() as db:

        return ExecutionLeaseRepository(db).renew(
            lease,
            duration_seconds=duration_seconds,
        )


def release_lease(lease) -> bool:

    with SessionLocal() as db:

        return ExecutionLeaseRepository(db).release(
            lease
        )


def main() -> None:

    print()
    print("STAGE 7.21D1 - EXECUTION LEASE RENEWAL")
    print("=====================================")

    session_id = create_test_session()

    try:

        # TEST 1: An active owner can renew its lease.

        lease_1 = acquire_lease(
            session_id,
            duration_seconds=120,
        )

        renewed_lease = renew_lease(
            lease_1,
            duration_seconds=240,
        )

        assert renewed_lease is not None

        assert renewed_lease.owner == lease_1.owner

        assert renewed_lease.version == lease_1.version

        assert renewed_lease.expires_at > lease_1.expires_at

        print("TEST 1 - Active lease renewal: PASSED")

        # TEST 2: An invalid owner cannot renew.

        invalid_owner = replace(
            renewed_lease,
            owner=str(uuid4()),
        )

        assert renew_lease(
            invalid_owner
        ) is None

        print("TEST 2 - Invalid owner rejected: PASSED")

        # TEST 3: A stale fencing version cannot renew.

        invalid_version = replace(
            renewed_lease,
            version=renewed_lease.version - 1,
        )

        assert renew_lease(
            invalid_version
        ) is None

        print("TEST 3 - Stale fencing version rejected: PASSED")

        # TEST 4: Released leases cannot be renewed.

        assert release_lease(
            renewed_lease
        ) is True

        assert renew_lease(
            renewed_lease
        ) is None

        print("TEST 4 - Released lease renewal rejected: PASSED")

        # TEST 5: Expired leases cannot be renewed.

        short_lease = acquire_lease(
            session_id,
            duration_seconds=1,
        )

        sleep(1.5)

        assert renew_lease(
            short_lease
        ) is None

        print("TEST 5 - Expired lease renewal rejected: PASSED")

        # TEST 6: A replacement owner can acquire an expired lease.

        replacement_lease = acquire_lease(
            session_id,
            duration_seconds=120,
        )

        assert replacement_lease.owner != short_lease.owner

        assert replacement_lease.version > short_lease.version

        assert renew_lease(
            short_lease
        ) is None

        assert release_lease(
            replacement_lease
        ) is True

        print("TEST 6 - Replacement ownership protected: PASSED")

        print()
        print("PASS")

    finally:

        delete_test_session(
            session_id
        )

        print(
            f"Disposable session removed: {session_id}"
        )


if __name__ == "__main__":

    main()
