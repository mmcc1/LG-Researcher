from control.control_service import (
    ControlService,
)

from control.control_context_factory import (
    ControlContextFactory,
)

from control.pause_command_handler import (
    PauseCommandHandler,
)

from domain.control import (
    ControlCommand,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from processing.control_command_validator import (
    ControlCommandValidator,
)

from processing.control_lifecycle_policy import (
    ControlLifecyclePolicy,
)


print()
print("PAUSE CONTROL SERVICE TEST")
print("==========================")


#
# -------------------------------------------------
# Fake Control Agent.
#
# We are testing ControlService routing here,
# not natural-language interpretation.
# -------------------------------------------------
#

class FakeControlAgent:

    def interpret(
        self,
        user_message,
        context,
    ):
        return ControlCommand(
            operation="pause",
        )


#
# -------------------------------------------------
# Handlers that must never be called by this test.
# -------------------------------------------------
#

class UnexpectedHandler:

    def execute(
        self,
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "Unexpected handler was called."
        )


#
# -------------------------------------------------
# Create a real researching session.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic="Pause control service test",
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
# Construct ControlService.
# -------------------------------------------------
#

control_service = ControlService(
    control_agent=FakeControlAgent(),
    context_factory=ControlContextFactory(
        session_factory=SessionLocal,
    ),
    command_validator=ControlCommandValidator(),
    lifecycle_policy=ControlLifecyclePolicy(),
    status_handler=UnexpectedHandler(),
    help_handler=UnexpectedHandler(),
    start_research_handler=UnexpectedHandler(),
    resume_handler=UnexpectedHandler(),
    generate_report_handler=UnexpectedHandler(),
    add_question_handler=UnexpectedHandler(),
    modify_scope_handler=UnexpectedHandler(),
    deeper_research_handler=UnexpectedHandler(),
    counter_evidence_handler=UnexpectedHandler(),
    pause_handler=PauseCommandHandler(
        session_factory=SessionLocal,
    ),
)


#
# -------------------------------------------------
# TEST 1
#
# Execute through ControlService.
# -------------------------------------------------
#

print()
print("TEST 1 - SERVICE ROUTING")
print("------------------------")


result = control_service.execute(
    user_message="Pause the research.",
    session_id=session_id,
)


assert (
    result.operation
    == "pause"
)

assert (
    result.success
    is True
)

assert (
    result.pause
    is not None
)

assert (
    result.pause.session_id
    == session_id
)

assert (
    result.pause.status
    == "researching"
)

assert (
    result.pause.pause_requested
    is True
)


print(
    f"Operation:       {result.operation}"
)

print(
    f"Message:         {result.message}"
)

print(
    f"Status:          {result.pause.status}"
)

print(
    f"Pause requested: "
    f"{result.pause.pause_requested}"
)


print(
    "Pause routed correctly: PASSED"
)


#
# -------------------------------------------------
# TEST 2
#
# ControlService must not claim that requesting
# pause means execution has already stopped.
# -------------------------------------------------
#

print()
print("TEST 2 - LIFECYCLE STATE")
print("------------------------")


assert (
    result.pause.status
    != "paused"
)


print(
    "Pause request distinct from "
    "paused state: PASSED"
)


#
# -------------------------------------------------
# TEST 3
#
# Verify durable SQL state independently.
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
    "SQL pause request: PASSED"
)

print(
    "SQL lifecycle unchanged: PASSED"
)


print()
print("==========================")
print("PASS")
print("==========================")

print(
    "ControlService correctly routes pause "
    "without falsely marking execution paused."
)