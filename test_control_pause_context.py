from control.control_context_factory import (
    ControlContextFactory,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


print()
print("CONTROL PAUSE CONTEXT TEST")
print("===========================")


factory = ControlContextFactory(
    session_factory=SessionLocal,
)


#
# -------------------------------------------------
# TEST 1
#
# No active session.
# -------------------------------------------------
#

print()
print("TEST 1 - NO SESSION")
print("-------------------")


context = factory.create(
    session_id=None,
)


assert context.session_id is None

assert (
    context.pause_requested
    is False
)


print(
    "No session has pause_requested=False: PASSED"
)


#
# -------------------------------------------------
# Create a real research session.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic="Control pause context test",
        )
    )

    session_id = (
        research_session.id
    )

    repository.set_status(
        session_id,
        "researching",
    )


print()
print(
    f"Session ID: {session_id}"
)


#
# -------------------------------------------------
# TEST 2
#
# Active session, not paused.
# -------------------------------------------------
#

print()
print("TEST 2 - ACTIVE")
print("---------------")


context = factory.create(
    session_id=session_id,
)


assert (
    context.session_id
    == session_id
)

assert (
    context.status
    == "researching"
)

assert (
    context.pause_requested
    is False
)


print(
    "Status is researching: PASSED"
)

print(
    "Pause request is False: PASSED"
)


#
# -------------------------------------------------
# TEST 3
#
# Request cooperative suspension.
# -------------------------------------------------
#

print()
print("TEST 3 - SUSPENDED")
print("------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.request_pause(
        session_id
    )


context = factory.create(
    session_id=session_id,
)


assert (
    context.status
    == "researching"
)

assert (
    context.pause_requested
    is True
)


print(
    "Lifecycle status remains researching: PASSED"
)

print(
    "Pause request exposed as True: PASSED"
)


#
# -------------------------------------------------
# TEST 4
#
# Clear suspension.
# -------------------------------------------------
#

print()
print("TEST 4 - RESUMED")
print("----------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.clear_pause_request(
        session_id
    )


context = factory.create(
    session_id=session_id,
)


assert (
    context.status
    == "researching"
)

assert (
    context.pause_requested
    is False
)


print(
    "Lifecycle status remains researching: PASSED"
)

print(
    "Pause request exposed as False: PASSED"
)


print()
print("===========================")
print("PASS")
print("===========================")

print(
    "ControlContext correctly exposes durable "
    "cooperative suspension independently of "
    "the research lifecycle status."
)