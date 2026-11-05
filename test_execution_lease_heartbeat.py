
from time import sleep

from persistence.database import SessionLocal
from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseUnavailable,
)
from persistence.research_session_repository import (
    ResearchSessionRepository,
)
from application.execution_lease_heartbeat import (
    ExecutionLeaseHeartbeat,
    ExecutionLeaseLost,
)


def main() -> None:

    print()
    print("STAGE 7.21D2 - EXECUTION LEASE HEARTBEAT")
    print("========================================")

    with SessionLocal() as db:

        session = ResearchSessionRepository(db).create(
            topic="Execution lease heartbeat integration test",
            scope="Disposable test session",
        )

        session_id = session.id

    heartbeat = None
    lease = None

    try:

        with SessionLocal() as db:

            lease = ExecutionLeaseRepository(db).acquire(
                session_id,
                duration_seconds=3,
            )

        heartbeat = ExecutionLeaseHeartbeat(
            session_factory=SessionLocal,
            lease=lease,
            duration_seconds=3,
            renewal_interval_seconds=0.5,
        )

        heartbeat.start()

        print("TEST 1 - Heartbeat started: PASSED")

        # Wait beyond the original three-second lease.
        sleep(5)

        heartbeat.check()

        with SessionLocal() as db:

            try:

                ExecutionLeaseRepository(db).acquire(
                    session_id,
                    duration_seconds=3,
                )

                raise AssertionError(
                    "Competing execution acquired an active lease."
                )

            except ExecutionLeaseUnavailable:

                pass

        print(
            "TEST 2 - Lease maintained beyond original expiry: PASSED"
        )

        print(
            "TEST 3 - Competing acquisition rejected: PASSED"
        )

        heartbeat.stop()
        heartbeat = None

        with SessionLocal() as db:

            released = ExecutionLeaseRepository(db).release(
                lease
            )

        assert released is True

        print("TEST 4 - Heartbeat stopped and lease released: PASSED")

        with SessionLocal() as db:

            replacement = ExecutionLeaseRepository(db).acquire(
                session_id,
                duration_seconds=3,
            )

            assert replacement.version > lease.version

            assert ExecutionLeaseRepository(db).release(
                replacement
            ) is True

        print("TEST 5 - New execution acquired lease: PASSED")

        print()
        print("PASS")

    finally:

        if heartbeat is not None:

            try:

                heartbeat.stop()

            except ExecutionLeaseLost:

                pass

        if lease is not None:

            with SessionLocal() as db:

                ExecutionLeaseRepository(db).release(
                    lease
                )

        # The session has no dependent research data.
        with SessionLocal() as db:

            session = ResearchSessionRepository(db).get(
                session_id
            )

            if session is not None:

                db.delete(session)
                db.commit()

        print(
            f"Disposable session removed: {session_id}"
        )


if __name__ == "__main__":

    main()
