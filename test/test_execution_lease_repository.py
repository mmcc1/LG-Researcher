"""Stage 7.21B SQL Server lease integration test.

Run from project root: python test_execution_lease_repository.py
Creates and deletes a disposable research session; does not run LangGraph.
"""

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from persistence.database import SessionLocal
from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseUnavailable,
)


def main():
    session_id = str(uuid4())
    print("STAGE 7.21B - EXECUTION LEASE TEST")
    print("===================================")

    try:
        with SessionLocal() as db:
            db.execute(text("""
                INSERT INTO dbo.research_sessions
                    (id, topic, scope, status, pause_requested, created_at, updated_at,
                     execution_owner, execution_lease_expires_at, execution_lease_version)
                VALUES
                    (:id, :topic, NULL, 'created', 0, SYSUTCDATETIME(), SYSUTCDATETIME(),
                     NULL, NULL, 0)
            """), {"id": session_id, "topic": "Stage 7.21B disposable lease test"})
            db.commit()

        with SessionLocal() as db:
            lease1 = ExecutionLeaseRepository(db).acquire(session_id, 120)
        assert lease1.version == 1
        print("TEST 1 - Initial acquisition: PASSED")

        with SessionLocal() as db:
            try:
                ExecutionLeaseRepository(db).acquire(session_id, 120)
            except ExecutionLeaseUnavailable:
                pass
            else:
                raise AssertionError("Concurrent acquisition unexpectedly succeeded")
        print("TEST 2 - Active lease rejects contender: PASSED")

        with SessionLocal() as db:
            assert ExecutionLeaseRepository(db).release(lease1)
        print("TEST 3 - Owner releases lease: PASSED")

        with SessionLocal() as db:
            lease2 = ExecutionLeaseRepository(db).acquire(session_id, 120)
        assert lease2.version == lease1.version + 1
        with SessionLocal() as db:
            assert not ExecutionLeaseRepository(db).release(lease1)
        print("TEST 4 - Old owner cannot release new lease: PASSED")

        # Simulate expiry by changing only the test session's expiry to a past
        # SQL Server UTC time. This does not require waiting 120 seconds.
        with SessionLocal() as db:
            db.execute(text("""
                UPDATE dbo.research_sessions
                SET execution_lease_expires_at = DATEADD(second, -1, SYSUTCDATETIME())
                WHERE id = :id AND execution_owner = :owner
                  AND execution_lease_version = :version
            """), {"id": session_id, "owner": lease2.owner, "version": lease2.version})
            db.commit()
        with SessionLocal() as db:
            lease3 = ExecutionLeaseRepository(db).acquire(session_id, 120)
        assert lease3.version == lease2.version + 1
        assert lease3.owner != lease2.owner
        with SessionLocal() as db:
            assert not ExecutionLeaseRepository(db).release(lease2)
            assert ExecutionLeaseRepository(db).release(lease3)
        print("TEST 5 - Expired lease reclaimed; stale release rejected: PASSED")
        print("\nPASS")
    finally:
        with SessionLocal() as db:
            db.execute(text("DELETE FROM dbo.research_sessions WHERE id = :id"), {"id": session_id})
            db.commit()
        print(f"Disposable session removed: {session_id}")


if __name__ == "__main__":
    main()
