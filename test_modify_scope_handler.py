from control.modify_scope_command_handler import (
    ModifyScopeCommandHandler,
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


print()
print(
    "MODIFY SCOPE HANDLER TEST"
)
print(
    "========================="
)


#
# -------------------------------------------------
# Create an isolated test session.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic=(
                "Test research topic for "
                "scope modification"
            )
        )
    )

    session_id = research_session.id

    repository.set_status(
        session_id=session_id,
        status="researching",
    )


print()
print(
    f"Test session: {session_id}"
)


handler = ModifyScopeCommandHandler(
    session_factory=SessionLocal,
)


#
# -------------------------------------------------
# TEST 1
# Initial scope assignment.
# -------------------------------------------------
#

print()
print("TEST 1 - SET SCOPE")
print("------------------")


context = ControlContext(
    session_id=session_id,
    topic=(
        "Test research topic for "
        "scope modification"
    ),
    scope=None,
    status="researching",
)


command = ControlCommand(
    operation="modify_scope",
    scope=(
        "Focus on technical architecture "
        "and implementation details."
    ),
)


result = handler.execute(
    command=command,
    context=context,
)


assert result.session_id == session_id

assert result.scope == (
    "Focus on technical architecture "
    "and implementation details."
)

assert result.status == "researching"


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    persisted = repository.get(
        session_id
    )

    assert persisted is not None

    assert persisted.scope == (
        "Focus on technical architecture "
        "and implementation details."
    )


print(
    "Initial scope assignment: PASSED"
)


#
# -------------------------------------------------
# TEST 2
# Replacement semantics.
# -------------------------------------------------
#

print()
print("TEST 2 - REPLACE SCOPE")
print("----------------------")


context = ControlContext(
    session_id=session_id,
    topic=result.topic,
    scope=result.scope,
    status="researching",
)


command = ControlCommand(
    operation="modify_scope",
    scope=(
        "Focus on economic incentives "
        "and market effects."
    ),
)


result = handler.execute(
    command=command,
    context=context,
)


assert result.scope == (
    "Focus on economic incentives "
    "and market effects."
)


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    persisted = repository.get(
        session_id
    )

    assert persisted is not None

    assert persisted.scope == (
        "Focus on economic incentives "
        "and market effects."
    )

    assert (
        "technical architecture"
        not in persisted.scope
    )


print(
    "Scope replacement semantics: PASSED"
)


#
# -------------------------------------------------
# TEST 3
# Empty scope rejected.
# -------------------------------------------------
#

print()
print("TEST 3 - EMPTY SCOPE")
print("--------------------")


try:

    handler.execute(
        command=ControlCommand(
            operation="modify_scope",
            scope="   ",
        ),
        context=ControlContext(
            session_id=session_id,
            topic=result.topic,
            scope=result.scope,
            status="researching",
        ),
    )

    raise AssertionError(
        "Empty scope was not rejected."
    )

except ValueError:

    pass


print(
    "Empty scope rejection: PASSED"
)


#
# -------------------------------------------------
# TEST 4
# Authoritative SQL lifecycle re-check.
# -------------------------------------------------
#

print()
print(
    "TEST 4 - STALE CONTEXT PROTECTION"
)
print(
    "---------------------------------"
)


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.set_status(
        session_id=session_id,
        status="reviewing",
    )


#
# Deliberately supply stale context claiming the
# session is still researching.
#

stale_context = ControlContext(
    session_id=session_id,
    topic=result.topic,
    scope=result.scope,
    status="researching",
)


try:

    handler.execute(
        command=ControlCommand(
            operation="modify_scope",
            scope=(
                "This must not be persisted."
            ),
        ),
        context=stale_context,
    )

    raise AssertionError(
        "Stale lifecycle context allowed "
        "an invalid scope mutation."
    )

except ValueError:

    pass


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    persisted = repository.get(
        session_id
    )

    assert persisted is not None

    assert persisted.status == "reviewing"

    assert persisted.scope == (
        "Focus on economic incentives "
        "and market effects."
    )


print(
    "Authoritative SQL lifecycle "
    "protection: PASSED"
)


print()
print(
    "========================="
)
print("PASS")
print(
    "========================="
)

print(
    "Modify-scope handler behaves "
    "as expected."
)