
#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

import time

from sqlalchemy import text

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


def create_test_session() -> str:

    with SessionLocal() as db:

        repository = ResearchSessionRepository(
            db
        )

        research_session = repository.create(
            topic="Execution lease recovery test",
            scope="Disposable database test session",
        )

        return research_session.id


def acquire_lease(
    session_id: str,
    duration_seconds: int,
) -> ExecutionLease:

    with SessionLocal() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        lease = repository.acquire(
            session_id=session_id,
            duration_seconds=duration_seconds,
        )

        return lease


def release_lease(
    lease: ExecutionLease,
) -> bool:

    with SessionLocal() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        return repository.release(
            lease
        )


def lease_is_valid(
    lease: ExecutionLease,
) -> bool:

    with SessionLocal() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        try:

            repository.fence(
                lease
            )

        except ExecutionLeaseFenceRejected:

            db.rollback()

            return False

        else:

            db.rollback()

            return True


def wait_for_expiry(
    lease: ExecutionLease,
    timeout_seconds: int = 15,
) -> None:

    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while time.monotonic() < deadline:

        if not lease_is_valid(
            lease
        ):

            return

        time.sleep(
            0.25
        )

    raise TimeoutError(
        "Execution lease did not expire "
        "within the expected interval."
    )


def set_reporting_status(
    session_id: str,
) -> None:

    with SessionLocal() as db:

        try:

            result = db.execute(
                text(
                    """
                    UPDATE dbo.research_sessions
                    SET status = 'reporting',
                        updated_at = SYSUTCDATETIME()
                    WHERE id = :session_id
                      AND status = 'created'
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            if result.rowcount != 1:

                raise RuntimeError(
                    "Could not prepare the disposable "
                    "session for recovery discovery."
                )

            db.commit()

        except Exception:

            db.rollback()
            raise


def get_recovery_candidates() -> list[str]:

    with SessionLocal() as db:

        repository = ResearchSessionRepository(
            db
        )

        return repository.find_recovery_candidates(
            limit=1000
        )


def delete_test_session(
    session_id: str,
) -> None:

    with SessionLocal() as db:

        try:

            result = db.execute(
                text(
                    """
                    DELETE FROM dbo.research_sessions
                    WHERE id = :session_id
                      AND topic = 'Execution lease recovery test'
                      AND status IN ('created', 'reporting')
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            if result.rowcount != 1:

                raise RuntimeError(
                    "Disposable session cleanup failed: "
                    f"{session_id}"
                )

            db.commit()

        except Exception:

            db.rollback()
            raise


def main():

    session_id = create_test_session()

    print()
    print(
        "EXECUTION LEASE EXPIRY AND RECOVERY TEST"
    )

    print()
    print(
        f"Disposable session: {session_id}"
    )

    try:

        first_lease = acquire_lease(
            session_id=session_id,
            duration_seconds=2,
        )

        assert lease_is_valid(
            first_lease
        )

        print(
            "Initial lease validity: PASSED"
        )

        wait_for_expiry(
            first_lease
        )

        print(
            "SQL Server lease expiry: PASSED"
        )

        assert not lease_is_valid(
            first_lease
        )

        print(
            "Expired lease fencing rejected: PASSED"
        )

        second_lease = acquire_lease(
            session_id=session_id,
            duration_seconds=120,
        )

        assert (
            second_lease.version
            == first_lease.version + 1
        )

        assert (
            second_lease.owner
            != first_lease.owner
        )

        print(
            "Expired lease reacquisition: PASSED"
        )

        assert not lease_is_valid(
            first_lease
        )

        print(
            "Previous owner fencing rejected: PASSED"
        )

        stale_release_result = release_lease(
            first_lease
        )

        assert stale_release_result is False

        assert lease_is_valid(
            second_lease
        )

        print(
            "Stale lease release rejected: PASSED"
        )

        set_reporting_status(
            session_id
        )

        candidates = get_recovery_candidates()

        assert session_id not in candidates, (
            "An actively leased reporting session "
            "was incorrectly eligible for recovery."
        )

        print(
            "Active reporting lease excluded: PASSED"
        )

        released = release_lease(
            second_lease
        )

        assert released

        candidates = get_recovery_candidates()

        assert session_id in candidates, (
            "Unowned reporting session was not "
            "discovered for recovery."
        )

        print(
            "Unowned reporting session discovered: PASSED"
        )

    finally:

        delete_test_session(
            session_id
        )

        print(
            "Disposable session cleanup: PASSED"
        )

    print()
    print(
        "Execution lease expiry and recovery: PASSED"
    )


if __name__ == "__main__":

    main()
