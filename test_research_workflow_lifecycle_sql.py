
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from persistence.database import engine

from persistence.models import ResearchSession

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
    RecoveryNotEligible,
)


TEST_DATABASE_NAME = "LGResearcher_Test"



@pytest.fixture
def test_environment():

    test_url = engine.url.set(
        database=TEST_DATABASE_NAME
    )

    if test_url.database != TEST_DATABASE_NAME:

        raise RuntimeError(
            "Integration tests must use "
            "LGResearcher_Test."
        )

    test_engine = create_engine(
        test_url,
        echo=False,
    )

    Session = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    session_ids = []

    try:

        yield Session, session_ids

    finally:

        try:

            with Session() as db:

                for session_id in session_ids:

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

        finally:

            test_engine.dispose()



def create_session(
    Session,
    session_ids,
    status: str,
    pause_requested: bool = False,
):

    session_id = str(uuid4())

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    with Session() as db:

        research_session = ResearchSession(
            id=session_id,
            topic="Lifecycle integration test",
            scope="Test scope",
            status=status,
            pause_requested=pause_requested,
            execution_lease_version=0,
            created_at=now,
            updated_at=now,
        )

        db.add(
            research_session
        )

        db.commit()

    session_ids.append(
        session_id
    )

    return session_id


def acquire_lease(
    Session,
    session_id,
):

    with Session() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        return repository.acquire(
            session_id
        )


def test_initial_execution_from_created(
    test_environment,
):

    Session, session_ids = test_environment

    session_id = create_session(
        Session,
        session_ids,
        status="created",
    )

    lease = acquire_lease(
        Session,
        session_id,
    )

    with Session() as db:

        repository = ResearchSessionRepository(
            db
        )

        topic, scope = (
            repository.prepare_execution_fenced(
                session_id=session_id,
                lease=lease,
                resume=False,
            )
        )

        assert topic == "Lifecycle integration test"
        assert scope == "Test scope"

    with Session() as db:

        research_session = db.get(
            ResearchSession,
            session_id,
        )

        assert research_session.status == "planning"


def test_initial_execution_from_planning_rejected(
    test_environment,
):

    Session, session_ids = test_environment

    session_id = create_session(
        Session,
        session_ids,
        status="planning",
    )

    lease = acquire_lease(
        Session,
        session_id,
    )

    with Session() as db:

        repository = ResearchSessionRepository(
            db
        )

        with pytest.raises(
            ValueError,
            match="cannot enter planning",
        ):

            repository.prepare_execution_fenced(
                session_id=session_id,
                lease=lease,
                resume=False,
            )


def test_initial_execution_with_pause_rejected(
    test_environment,
):

    Session, session_ids = test_environment

    session_id = create_session(
        Session,
        session_ids,
        status="created",
        pause_requested=True,
    )

    lease = acquire_lease(
        Session,
        session_id,
    )

    with Session() as db:

        repository = ResearchSessionRepository(
            db
        )

        with pytest.raises(
            RecoveryNotEligible
        ):

            repository.prepare_execution_fenced(
                session_id=session_id,
                lease=lease,
                resume=False,
            )


@pytest.mark.parametrize(
    "status",
    [
        "researched",
        "reviewed",
    ],
)
def test_recovery_from_completed_phase(
    test_environment,
    status,
):

    Session, session_ids = test_environment

    session_id = create_session(
        Session,
        session_ids,
        status=status,
    )

    lease = acquire_lease(
        Session,
        session_id,
    )

    with Session() as db:

        repository = ResearchSessionRepository(
            db
        )

        topic, scope = (
            repository.prepare_recovery_execution_fenced(
                session_id=session_id,
                lease=lease,
            )
        )

        assert topic == "Lifecycle integration test"
        assert scope == "Test scope"


def test_recovery_with_pause_rejected(
    test_environment,
):

    Session, session_ids = test_environment

    session_id = create_session(
        Session,
        session_ids,
        status="researching",
        pause_requested=True,
    )

    lease = acquire_lease(
        Session,
        session_id,
    )

    with Session() as db:

        repository = ResearchSessionRepository(
            db
        )

        with pytest.raises(
            RecoveryNotEligible
        ):

            repository.prepare_recovery_execution_fenced(
                session_id=session_id,
                lease=lease,
            )


def test_stale_initial_execution_decision_rejected(
    test_environment,
):

    Session, session_ids = test_environment

    session_id = create_session(
        Session,
        session_ids,
        status="created",
    )

    # Simulate a worker reading "created" before
    # another execution advances the lifecycle.

    with Session() as db:

        research_session = db.get(
            ResearchSession,
            session_id,
        )

        assert research_session.status == "created"

    # Another execution advances the session.

    with Session() as db:

        research_session = db.get(
            ResearchSession,
            session_id,
        )

        research_session.status = "planning"

        db.commit()

    # The stale worker now acquires a valid lease
    # but must not restart initial execution.

    lease = acquire_lease(
        Session,
        session_id,
    )

    with Session() as db:

        repository = ResearchSessionRepository(
            db
        )

        with pytest.raises(
            ValueError,
            match="cannot enter planning",
        ):

            repository.prepare_execution_fenced(
                session_id=session_id,
                lease=lease,
                resume=False,
            )
