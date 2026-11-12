from agents.control_agent import (
    ControlAgent,
)

from domain.control import (
    ControlContext,
)
from models.factory import ChatModelFactory
from config import settings

from processing.control_command_validator import (
    ControlCommandValidator,
)

from processing.control_lifecycle_policy import (
    ControlLifecyclePolicy,
)


lifecycle_policy = ControlLifecyclePolicy()

validator = ControlCommandValidator()


control_agent = ControlAgent(
    model=ChatModelFactory.create(
            settings.controller_model
    )
)


context = ControlContext(
    session_id=(
        "063bd913-9e9a-48bd-81d7-8738153a7863"
    ),
    topic="What is Bitcoin?",
    status="completed",
)


tests = [
    "What is the status of this research?",

    "Investigate the environmental impact "
    "of Bitcoin mining in more detail.",

    "Look for evidence that challenges the "
    "claim that Bitcoin is an inflation hedge.",

    "Add a question about the energy consumed "
    "by Bitcoin mining.",

    "Generate the report.",

    "Pause the research.",

    "Resume it.",

    "What can you do?",

    "Start new research into quantum computing, "
    
    "focusing specifically on fault-tolerant "
    
    "quantum computing."
]


for user_message in tests:

    print()
    print("=" * 70)

    print(
        f"USER: {user_message}"
    )

    raw_command = (
        control_agent.interpret(
            user_message=user_message,
            context=context,
        )
    )

    print()
    print("RAW COMMAND")

    print(
        raw_command.model_dump_json(
            indent=2
        )
    )

    try:

        command = validator.validate(
            command=raw_command,
            context=context,
        )

    except ValueError as error:

        print()
        print("COMMAND REJECTED:")
        print(error)

        continue

    print()
    print("VALIDATED COMMAND")

    print(
        command.model_dump_json(
            indent=2
        )
    )

    try:

        lifecycle_policy.validate(
            command=command,
            context=context,
        )

        print()
        print(
            "LIFECYCLE POLICY: ALLOWED"
        )

    except ValueError as error:

        print()
        print(
            "LIFECYCLE POLICY: REJECTED"
        )

        print(error)