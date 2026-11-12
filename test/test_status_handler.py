from control.status_command_handler import (
    StatusCommandHandler,
)

from domain.control import (
    ControlContext,
)

from persistence.database import (
    SessionLocal,
)


SESSION_ID = (
    "063bd913-9e9a-48bd-81d7-8738153a7863"
)


handler = StatusCommandHandler(
    session_factory=SessionLocal,
)


context = ControlContext(
    session_id=SESSION_ID,
    topic="What is Bitcoin?",
    status="completed",
)


result = handler.execute(
    context=context,
)


print()
print(
    "RESEARCH STATUS"
)
print(
    "==============="
)

print(
    result.model_dump_json(
        indent=2
    )
)