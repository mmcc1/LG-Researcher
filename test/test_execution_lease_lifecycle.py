
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

from dataclasses import replace

from sqlalchemy import text

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
    ExecutionLeaseUnavailable,
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
            topic="Execution lease lifecycle test",
            scope="Disposable database test session",
        )

        return research_session.id


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
                      AND status = 'created'
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            if result.rowcount != 1:

                raise RuntimeError(
                    "Test session cleanup failed. "
                    f"Session ID: {session_id}"
                )

            db.commit()

        except Exception:

            db.rollback()
            raise


def acquire_lease(
    session_id: str,
) -> ExecutionLease:

    with SessionLocal() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        return repository.acquire(
            session_id=session_id,
            duration_seconds=120,
        )


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


def assert_fence_rejected(
    lease: ExecutionLease,
) -> None:

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

            return

        else:

            db.rollback()

            raise AssertionError(
                "Expected lease fencing rejection."
            )


def assert_fence_accepted(
    lease: ExecutionLease,
) -> None:

    with SessionLocal() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        repository.fence(
            lease
        )

        db.rollback()


def assert_completion_rejected(
    lease: ExecutionLease,
    expected_exception: type[Exception],
) -> None:

    with SessionLocal() as db:

        repository = ResearchSessionRepository(
            db
        )

        try:

            repository.complete_report_fenced(
                session_id=lease.session_id,
                lease=lease,
            )

        except expected_exception:

            db.rollback()

            return

        else:

            db.rollback()

            raise AssertionError(
                "Unexpected successful report completion."
            )


def assert_session_created(
    session_id: str,
) -> None:

    with SessionLocal() as db:

        repository = ResearchSessionRepository(
            db
        )

        research_session = repository.get(
            session_id
        )

        assert research_session is not None

        assert research_session.status == "created", (
            "Test session status changed unexpectedly."
        )


def main():

    session_id = create_test_session()

    print()
    print(
        "EXECUTION LEASE LIFECYCLE TEST"
    )

    print()
    print(
        f"Disposable session: {session_id}"
    )

    try:

        first_lease = acquire_lease(
            session_id
        )

        assert first_lease.session_id == session_id

        assert first_lease.owner

        assert first_lease.version >= 1

        print(
            "Lease acquisition: PASSED"
        )

        try:

            acquire_lease(
                session_id
            )

        except ExecutionLeaseUnavailable:

            print(
                "Competing acquisition rejected: PASSED"
            )

        else:

            raise AssertionError(
                "Competing lease acquisition succeeded."
            )

        assert_fence_accepted(
            first_lease
        )

        print(
            "Valid lease fencing: PASSED"
        )

        invalid_owner_lease = replace(
            first_lease,
            owner="invalid-test-owner",
        )

        assert_fence_rejected(
            invalid_owner_lease
        )

        print(
            "Invalid owner fencing: PASSED"
        )

        invalid_version_lease = replace(
            first_lease,
            version=first_lease.version + 1,
        )

        assert_fence_rejected(
            invalid_version_lease
        )

        print(
            "Invalid version fencing: PASSED"
        )

        assert_completion_rejected(
            first_lease,
            ValueError,
        )

        print(
            "Completion from created state rejected: PASSED"
        )

        released = release_lease(
            first_lease
        )

        assert released, (
            "First execution lease was not released."
        )

        print(
            "Lease release: PASSED"
        )

        second_lease = acquire_lease(
            session_id
        )

        assert second_lease.owner != first_lease.owner

        assert (
            second_lease.version
            == first_lease.version + 1
        )

        print(
            "Lease reacquisition and version increment: PASSED"
        )

        assert_fence_rejected(
            first_lease
        )

        print(
            "Stale lease fencing: PASSED"
        )

        assert_completion_rejected(
            first_lease,
            ExecutionLeaseFenceRejected,
        )

        print(
            "Stale lease completion rejected: PASSED"
        )

        assert_fence_accepted(
            second_lease
        )

        print(
            "Replacement lease fencing: PASSED"
        )

        released = release_lease(
            second_lease
        )

        assert released, (
            "Second execution lease was not released."
        )

        assert_session_created(
            session_id
        )

        print(
            "Session state unchanged: PASSED"
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
        "Execution lease lifecycle: PASSED"
    )


if __name__ == "__main__":

    main()
