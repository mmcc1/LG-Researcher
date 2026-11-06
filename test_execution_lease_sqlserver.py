
import os

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

import pytest

from sqlalchemy import (
    text,
)

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseUnavailable,
    ExecutionLeaseFenceRejected,
)

from concurrent.futures import (
    ThreadPoolExecutor,
)

from threading import (
    Event,
)

from sqlalchemy.exc import (
    DBAPIError,
)


pytestmark = pytest.mark.skipif(
    os.environ.get(
        "RUN_SQLSERVER_INTEGRATION_TESTS"
    ) != "1",
    reason=(
        "SQL Server integration tests are disabled."
    ),
)


@pytest.fixture
def research_session_id():

    session_id = str(
        uuid4()
    )

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    with SessionLocal() as db:

        db.execute(
            text(
                """
                INSERT INTO dbo.research_sessions (
                    id,
                    topic,
                    status,
                    pause_requested,
                    created_at,
                    updated_at
                )
                VALUES (
                    :session_id,
                    :topic,
                    :status,
                    :pause_requested,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "session_id": session_id,
                "topic": (
                    "Execution lease integration test"
                ),
                "status": "created",
                "pause_requested": False,
                "created_at": now,
                "updated_at": now,
            },
        )

        db.commit()

    try:

        yield session_id

    finally:

        with SessionLocal() as db:

            db.execute(
                text(
                    """
                    DELETE FROM dbo.research_sessions
                    WHERE id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            db.commit()


def test_active_lease_prevents_second_acquisition(
    research_session_id,
):

    session_id = research_session_id

    with SessionLocal() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        first_lease = repository.acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    with SessionLocal() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        with pytest.raises(
            ExecutionLeaseUnavailable
        ):

            repository.acquire(
                session_id=session_id,
                duration_seconds=120,
            )

    assert first_lease.version >= 1


def test_expired_lease_can_be_reacquired(
    research_session_id,
):

    session_id = research_session_id

    with SessionLocal() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        first_lease = repository.acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    with SessionLocal() as db:

        db.execute(
            text(
                """
                UPDATE dbo.research_sessions
                SET execution_lease_expires_at =
                    DATEADD(
                        second,
                        -1,
                        SYSUTCDATETIME()
                    )
                WHERE id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        )

        db.commit()

    with SessionLocal() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        second_lease = repository.acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    assert second_lease.owner != first_lease.owner

    assert second_lease.version == (
        first_lease.version + 1
    )


def test_superseded_lease_cannot_pass_fence(
    research_session_id,
):

    session_id = research_session_id

    with SessionLocal() as db:

        first_lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    with SessionLocal() as db:

        db.execute(
            text(
                """
                UPDATE dbo.research_sessions
                SET execution_lease_expires_at =
                    DATEADD(
                        second,
                        -1,
                        SYSUTCDATETIME()
                    )
                WHERE id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        )

        db.commit()

    with SessionLocal() as db:

        second_lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    with SessionLocal() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        with pytest.raises(
            ExecutionLeaseFenceRejected
        ):

            repository.fence(
                first_lease
            )

    assert second_lease.version > first_lease.version


def test_superseded_lease_cannot_release_new_owner(
    research_session_id,
):

    session_id = research_session_id

    with SessionLocal() as db:

        first_lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    with SessionLocal() as db:

        db.execute(
            text(
                """
                UPDATE dbo.research_sessions
                SET execution_lease_expires_at =
                    DATEADD(
                        second,
                        -1,
                        SYSUTCDATETIME()
                    )
                WHERE id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        )

        db.commit()

    with SessionLocal() as db:

        second_lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    with SessionLocal() as db:

        released = ExecutionLeaseRepository(
            db
        ).release(
            first_lease
        )

    assert released is False

    with SessionLocal() as db:

        row = db.execute(
            text(
                """
                SELECT
                    execution_owner,
                    execution_lease_version
                FROM dbo.research_sessions
                WHERE id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        ).first()

    assert row is not None

    assert row.execution_owner == second_lease.owner

    assert row.execution_lease_version == second_lease.version



def test_execution_fence_blocks_competing_acquisition(
    research_session_id,
):

    session_id = research_session_id

    with SessionLocal() as db:

        first_lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=2,
        )

    fence_acquired = Event()

    release_fence = Event()

    def hold_execution_fence():

        with SessionLocal() as db:

            repository = ExecutionLeaseRepository(
                db
            )

            try:

                repository.fence(
                    first_lease
                )

                fence_acquired.set()

                if not release_fence.wait(
                    timeout=10
                ):

                    raise TimeoutError(
                        "Timed out waiting to release "
                        "the execution fence."
                    )

                db.commit()

            except Exception:

                db.rollback()
                raise

    def attempt_competing_acquisition():

        with SessionLocal() as db:

            db.execute(
                text(
                    "SET LOCK_TIMEOUT 1000"
                )
            )

            db.commit()

            repository = ExecutionLeaseRepository(
                db
            )

            return repository.acquire(
                session_id=session_id,
                duration_seconds=120,
            )

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:

        fence_future = executor.submit(
            hold_execution_fence
        )

        try:

            assert fence_acquired.wait(
                timeout=5
            )

            # The fence remains held while the
            # original lease expires.
            #
            # SQL Server should prevent a second
            # worker from updating the locked row.

            from time import sleep

            sleep(2.5)

            acquisition_future = executor.submit(
                attempt_competing_acquisition
            )

            with pytest.raises(
                DBAPIError
            ):

                acquisition_future.result(
                    timeout=5
                )

        finally:

            release_fence.set()

            fence_future.result(
                timeout=10
            )
