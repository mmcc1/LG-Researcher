from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


print()
print("PAUSE PERSISTENCE TEST")
print("======================")


#
# -------------------------------------------------
# TEST 1
#
# New sessions must not start with a pause request.
# -------------------------------------------------
#

print()
print("TEST 1 - INITIAL STATE")
print("----------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic="Pause persistence test",
        )
    )

    session_id = (
        research_session.id
    )

    assert (
        research_session.pause_requested
        is False
    )

    print(
        f"Session ID: {session_id}"
    )

    print(
        "Initial pause request: False"
    )


print(
    "Initial pause state: PASSED"
)


#
# -------------------------------------------------
# TEST 2
#
# Verify the value is durable, not merely present
# on the original SQLAlchemy object.
# -------------------------------------------------
#

print()
print("TEST 2 - DURABLE INITIAL STATE")
print("------------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.get(
            session_id
        )
    )

    assert (
        research_session
        is not None
    )

    assert (
        research_session.pause_requested
        is False
    )


print(
    "Durable initial pause state: PASSED"
)


print()
print("======================")
print("PASS")
print("======================")