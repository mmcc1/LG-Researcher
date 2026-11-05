from control.control_context_factory import (
    ControlContextFactory,
)

from control.status_command_handler import (
    StatusCommandHandler,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


print()
print("PAUSE STATUS TEST")
print("=================")


context_factory = ControlContextFactory(
    session_factory=SessionLocal,
)

handler = StatusCommandHandler(
    session_factory=SessionLocal,
)


#
# -------------------------------------------------
# Create an active research session.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic="Pause status test",
        )
    )

    session_id = (
        research_session.id
    )

    repository.set_status(
        session_id,
        "researching",
    )


print(
    f"Session ID: {session_id}"
)


#
# -------------------------------------------------
# TEST 1
#
# Active session with no pause request.
# -------------------------------------------------
#

print()
print("TEST 1 - RUNNING")
print("----------------")


context = context_factory.create(
    session_id=session_id,
)

result = handler.execute(
    context=context,
)


assert (
    result.status
    == "researching"
)

assert (
    result.pause_requested
    is False
)


print(
    "Status is researching: PASSED"
)

print(
    "Pause requested is False: PASSED"
)


#
# -------------------------------------------------
# TEST 2
#
# Request cooperative suspension.
# -------------------------------------------------
#

print()
print("TEST 2 - PAUSE REQUESTED")
print("------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.request_pause(
        session_id
    )


context = context_factory.create(
    session_id=session_id,
)

result = handler.execute(
    context=context,
)


assert (
    result.status
    == "researching"
)

assert (
    result.pause_requested
    is True
)


print(
    "Status remains researching: PASSED"
)

print(
    "Pause requested is True: PASSED"
)


#
# -------------------------------------------------
# TEST 3
#
# Prove StatusCommandHandler reads authoritative
# SQL rather than trusting the ControlContext
# snapshot.
#
# Create the context while paused, then clear the
# durable flag before executing the handler.
# -------------------------------------------------
#

print()
print("TEST 3 - AUTHORITATIVE SQL")
print("--------------------------")


stale_context = (
    context_factory.create(
        session_id=session_id,
    )
)


assert (
    stale_context.pause_requested
    is True
)


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.clear_pause_request(
        session_id
    )


result = handler.execute(
    context=stale_context,
)


assert (
    stale_context.pause_requested
    is True
)

assert (
    result.pause_requested
    is False
)


print(
    "Context snapshot is stale True: PASSED"
)

print(
    "Status returned current SQL False: PASSED"
)


print()
print("=================")
print("PASS")
print("=================")

print(
    "Status exposes the authoritative durable "
    "pause request independently of lifecycle "
    "status."
)