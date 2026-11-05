from nodes.check_pause import (
    CheckPauseNode,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


print()
print("CHECK PAUSE NODE TEST")
print("=====================")


#
# -------------------------------------------------
# Create session.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic="Check pause node test",
        )
    )

    session_id = (
        research_session.id
    )


print(
    f"Session ID: {session_id}"
)


node = CheckPauseNode(
    session_factory=SessionLocal,
)


#
# -------------------------------------------------
# Minimal state.
#
# CheckPauseNode only requires session_id.
# -------------------------------------------------
#

state = {
    "session_id": session_id,
}


#
# -------------------------------------------------
# TEST 1
#
# No pause request exists.
# -------------------------------------------------
#

print()
print("TEST 1 - NOT PAUSED")
print("-------------------")


result = node(state)


assert (
    result["pause_requested"]
    is False
)


print(
    "Node returned pause_requested=False: "
    "PASSED"
)


#
# -------------------------------------------------
# TEST 2
#
# Request pause in durable SQL.
# -------------------------------------------------
#

print()
print("TEST 2 - REQUEST PAUSE")
print("----------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.request_pause(
        session_id
    )


result = node(state)


assert (
    result["pause_requested"]
    is True
)


print(
    "Node returned pause_requested=True: "
    "PASSED"
)


#
# -------------------------------------------------
# TEST 3
#
# The node must be read-only.
# -------------------------------------------------
#

print()
print("TEST 3 - NODE IS READ ONLY")
print("--------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    assert (
        repository.is_pause_requested(
            session_id
        )
        is True
    )


print(
    "Durable pause request remains True: "
    "PASSED"
)


#
# -------------------------------------------------
# TEST 4
#
# Clear the request and verify that the node
# observes the new durable value.
# -------------------------------------------------
#

print()
print("TEST 4 - CLEAR PAUSE")
print("--------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.clear_pause_request(
        session_id
    )


result = node(state)


assert (
    result["pause_requested"]
    is False
)


print(
    "Node observed cleared pause request: "
    "PASSED"
)


print()
print("=====================")
print("PASS")
print("=====================")

print(
    "CheckPauseNode correctly observes the "
    "durable pause request without modifying it."
)