from control.pause_command_handler import (
    PauseCommandHandler,
)

from domain.control import (
    ControlCommand,
    ControlContext,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from processing.control_lifecycle_policy import (
    ControlLifecyclePolicy,
)


print()
print("PAUSE HANDLER TEST")
print("==================")


policy = ControlLifecyclePolicy()

handler = PauseCommandHandler(
    session_factory=SessionLocal
)


#
# -------------------------------------------------
# Create an actively researching session.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic="Pause handler test",
        )
    )

    session_id = research_session.id

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
# Lifecycle policy accepts pause while researching.
# -------------------------------------------------
#

print()
print("TEST 1 - LIFECYCLE POLICY")
print("-------------------------")


command = ControlCommand(
    operation="pause",
)

context = ControlContext(
    session_id=session_id,
    topic="Pause handler test",
    scope=None,
    status="researching",
)


policy.validate(
    command=command,
    context=context,
)


print(
    "Researching pause accepted: PASSED"
)


#
# -------------------------------------------------
# TEST 2
#
# Handler records request but MUST NOT claim the
# workflow has already paused.
# -------------------------------------------------
#

print()
print("TEST 2 - PAUSE REQUEST")
print("----------------------")


result = handler.execute(
    command=command,
    session_id=session_id,
)


assert (
    result.session_id
    == session_id
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
    f"Result status: "
    f"{result.status}"
)

print(
    f"Pause requested: "
    f"{result.pause_requested}"
)

print(
    "Pause request recorded: PASSED"
)

print(
    "Status remains researching: PASSED"
)


#
# -------------------------------------------------
# TEST 3
#
# Verify authoritative durable SQL state.
# -------------------------------------------------
#

print()
print("TEST 3 - SQL STATE")
print("------------------")


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
        research_session.status
        == "researching"
    )

    assert (
        research_session.pause_requested
        is True
    )


print(
    "Durable pause request: PASSED"
)

print(
    "Lifecycle status unchanged: PASSED"
)


#
# -------------------------------------------------
# TEST 4
#
# Completed sessions must be rejected by policy.
# -------------------------------------------------
#

print()
print("TEST 4 - COMPLETED POLICY")
print("-------------------------")


completed_context = ControlContext(
    session_id=session_id,
    topic="Pause handler test",
    scope=None,
    status="completed",
)


try:

    policy.validate(
        command=command,
        context=completed_context,
    )

    raise AssertionError(
        "Completed pause should have failed."
    )

except ValueError:

    print(
        "Completed pause rejected: PASSED"
    )


#
# -------------------------------------------------
# TEST 5
#
# Handler must independently reject stale context.
#
# Context says researching, but authoritative SQL
# now says completed.
# -------------------------------------------------
#

print()
print("TEST 5 - STALE CONTEXT")
print("----------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.set_status(
        session_id,
        "completed",
    )


try:

    handler.execute(
        command=command,
        session_id=session_id,
    )

    raise AssertionError(
        "Stale pause should have failed."
    )

except ValueError:

    pass


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
        research_session.status
        == "completed"
    )


print(
    "Authoritative SQL recheck: PASSED"
)


print()
print("==================")
print("PASS")
print("==================")

print(
    "Pause control handler records a durable "
    "pause request without falsely marking "
    "the workflow paused."
)