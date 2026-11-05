from agents.control_agent import (
    ControlAgent,
)

from control.control_service import (
    ControlService,
)

from control.status_command_handler import (
    StatusCommandHandler,
)


from persistence.database import (
    SessionLocal,
)

from processing.control_command_validator import (
    ControlCommandValidator,
)

from processing.control_lifecycle_policy import (
    ControlLifecyclePolicy,
)

from models.factory import ChatModelFactory
from config import settings

from control.control_context_factory import (
    ControlContextFactory,
)

from control.help_command_handler import (
    HelpCommandHandler,
)


SESSION_ID = (
    "063bd913-9e9a-48bd-81d7-8738153a7863"
)


control_agent = ControlAgent(
    model=ChatModelFactory.create(
            settings.controller_model
    )
)


control_service = ControlService(
    control_agent=control_agent,

    context_factory=(
        ControlContextFactory(
            session_factory=SessionLocal,
        )
    ),

    command_validator=(
        ControlCommandValidator()
    ),

    lifecycle_policy=(
        ControlLifecyclePolicy()
    ),

    status_handler=(
        StatusCommandHandler(
            session_factory=SessionLocal,
        )
    ),

    help_handler=(
        HelpCommandHandler()
    ),
)


result = control_service.execute(
    user_message=(
        "What is the status of "
        "this research?"
    ),
    session_id=SESSION_ID,
)


print()
print(
    "CONTROL SERVICE RESULT"
)
print(
    "======================"
)

print(
    result.model_dump_json(
        indent=2
    )
)


result = control_service.execute(
    user_message=(
        "What can you do?"
    ),
    session_id=SESSION_ID,
)


print()
print(
    "CONTROL HELP RESULT"
)
print(
    "==================="
)

print(
    result.model_dump_json(
        indent=2
    )
)