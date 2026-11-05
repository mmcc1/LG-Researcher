
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from sqlalchemy import text

from persistence.database import SessionLocal
from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)
from persistence.research_session_repository import (
    ResearchSessionRepository,
)


def make_session():

    with SessionLocal() as db:

        return ResearchSessionRepository(db).create(
            topic="Execution fencing test",
            scope=None,
        ).id


def delete_session(session_id):

    with SessionLocal() as db:

        record = ResearchSessionRepository(db).get(
            session_id
        )

        if record is not None:

            db.delete(record)
            db.commit()


def expect_fence_rejected(lease):

    with SessionLocal() as db:

        try:

            ExecutionLeaseRepository(db).fence(
                lease
            )

        except ExecutionLeaseFenceRejected:

            return

        raise AssertionError(
            "Execution fencing unexpectedly succeeded."
        )


def main():

    print()
    print("EXECUTION LEASE FENCING")
    print("=======================")

    session_id = make_session()

    try:

        with SessionLocal() as db:

            lease = ExecutionLeaseRepository(db).acquire(
                session_id,
                duration_seconds=30,
            )

        with SessionLocal() as db:

            ExecutionLeaseRepository(db).fence(
                lease
            )

            db.commit()

        print(
            "TEST 1 - Valid owner accepted: PASSED"
        )

        incorrect_owner = ExecutionLease(
            session_id=lease.session_id,
            owner="incorrect-owner",
            version=lease.version,
            expires_at=lease.expires_at,
        )

        expect_fence_rejected(
            incorrect_owner
        )

        print(
            "TEST 2 - Incorrect owner rejected: PASSED"
        )

        incorrect_version = ExecutionLease(
            session_id=lease.session_id,
            owner=lease.owner,
            version=lease.version - 1,
            expires_at=lease.expires_at,
        )

        expect_fence_rejected(
            incorrect_version
        )

        print(
            "TEST 3 - Incorrect version rejected: PASSED"
        )

        with SessionLocal() as db:

            try:

                db.execute(
                    text("""
                        UPDATE dbo.research_sessions
                        SET topic = :topic
                        WHERE id = :session_id
                    """),
                    {
                        "topic": "Uncommitted change",
                        "session_id": session_id,
                    },
                )

                ExecutionLeaseRepository(db).fence(
                    incorrect_owner
                )

            except ExecutionLeaseFenceRejected:

                pass

            else:

                raise AssertionError(
                    "Expected fencing rejection."
                )

        with SessionLocal() as db:

            record = ResearchSessionRepository(db).get(
                session_id
            )

            assert record.topic == (
                "Execution fencing test"
            )

        print(
            "TEST 4 - Rejected transaction rolled back: PASSED"
        )

        lock_acquired = Event()
        release_lock = Event()
        contender_started = Event()

        def hold_fence():

            with SessionLocal() as db:

                ExecutionLeaseRepository(db).fence(
                    lease
                )

                lock_acquired.set()

                if not release_lock.wait(timeout=10):

                    raise TimeoutError(
                        "Fence holder was not released."
                    )

                db.commit()

        def attempt_acquisition():

            contender_started.set()

            with SessionLocal() as db:

                return ExecutionLeaseRepository(db).acquire(
                    session_id,
                    duration_seconds=30,
                )

        with ThreadPoolExecutor(max_workers=2) as pool:

            holder = pool.submit(
                hold_fence
            )

            try:

                assert lock_acquired.wait(timeout=10)

                contender = pool.submit(
                    attempt_acquisition
                )

                assert contender_started.wait(timeout=10)

                try:

                    contender.result(timeout=1)

                except TimeoutError:

                    pass

                else:

                    raise AssertionError(
                        "Competing acquisition completed "
                        "while the fence was held."
                    )

            finally:

                release_lock.set()

            holder.result(timeout=10)

            try:

                contender.result(timeout=10)

            except Exception as exc:

                from persistence.execution_lease_repository import (
                    ExecutionLeaseUnavailable,
                )

                assert isinstance(
                    exc,
                    ExecutionLeaseUnavailable,
                ), str(exc)

            else:

                raise AssertionError(
                    "Competing acquisition unexpectedly succeeded."
                )

        print(
            "TEST 5 - Fence blocks competing acquisition: PASSED"
        )

        with SessionLocal() as db:

            assert ExecutionLeaseRepository(db).release(
                lease
            ) is True

        with SessionLocal() as db:

            expired_lease = ExecutionLeaseRepository(db).acquire(
                session_id,
                duration_seconds=30,
            )

        with SessionLocal() as db:

            db.execute(
                text("""
                    UPDATE dbo.research_sessions
                    SET execution_lease_expires_at =
                        DATEADD(
                            second,
                            -1,
                            SYSUTCDATETIME()
                        )
                    WHERE id = :session_id
                """),
                {
                    "session_id": session_id,
                },
            )

            db.commit()

        expect_fence_rejected(
            expired_lease
        )

        print(
            "TEST 6 - Expired lease rejected: PASSED"
        )

        with SessionLocal() as db:

            replacement = ExecutionLeaseRepository(db).acquire(
                session_id,
                duration_seconds=30,
            )

        expect_fence_rejected(
            expired_lease
        )

        with SessionLocal() as db:

            assert ExecutionLeaseRepository(db).release(
                replacement
            ) is True

        print(
            "TEST 7 - Superseded execution rejected: PASSED"
        )

        print()
        print("PASS")

    finally:

        delete_session(
            session_id
        )

        print(
            f"Disposable session removed: {session_id}"
        )


if __name__ == "__main__":

    main()
