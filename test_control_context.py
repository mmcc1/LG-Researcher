from control.control_context_factory import (
    ControlContextFactory,
)

from persistence.database import (
    SessionLocal,
)


SESSION_ID = (
    "063bd913-9e9a-48bd-81d7-8738153a7863"
)


factory = ControlContextFactory(
    session_factory=SessionLocal,
)


print()
print(
    "ACTIVE SESSION CONTEXT"
)
print(
    "======================"
)

context = factory.create(
    SESSION_ID
)

print(
    context.model_dump_json(
        indent=2
    )
)


print()
print(
    "NO ACTIVE SESSION CONTEXT"
)
print(
    "========================="
)

context = factory.create(
    None
)

print(
    context.model_dump_json(
        indent=2
    )
)