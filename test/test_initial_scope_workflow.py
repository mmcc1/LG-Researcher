from application.research_workflow_service import (
    ResearchWorkflowService,
)

from control.start_research_command_handler import (
    StartResearchCommandHandler,
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

from processing.control_command_validator import (
    ControlCommandValidator,
)


print()
print("INITIAL SCOPE WORKFLOW TEST")
print("===========================")


class FakeGraph:

    def __init__(self):
        self.state = None

    def invoke(
        self,
        state,
    ):
        self.state = state

        #
        # Simulate successful completion so the
        # command handler can reload authoritative
        # lifecycle state afterward.
        #

        with SessionLocal() as db:

            repository = (
                ResearchSessionRepository(db)
            )

            repository.set_status(
                state["session_id"],
                "completed",
            )

        return state


#
# -------------------------------------------------
# Inputs
# -------------------------------------------------
#

topic = (
    "The effect of Bitcoin mining "
    "on energy systems"
)

scope = (
    "Focus specifically on electricity pricing, "
    "grid incentives, and renewable-energy "
    "investment."
)


#
# -------------------------------------------------
# Construct the deterministic production path.
#
# Real:
#   validator
#   command handler
#   workflow service
#   repository
#   SQL
#
# Fake:
#   graph execution
# -------------------------------------------------
#

fake_graph = FakeGraph()

workflow_service = (
    ResearchWorkflowService(
        graph=fake_graph,
        session_factory=SessionLocal,
    )
)

handler = (
    StartResearchCommandHandler(
        workflow_service=workflow_service,
        session_factory=SessionLocal,
    )
)

validator = (
    ControlCommandValidator()
)


#
# -------------------------------------------------
# Create and validate the control command.
# -------------------------------------------------
#

print()
print("TEST 1 - COMMAND VALIDATION")
print("---------------------------")


command = ControlCommand(
    operation="start_research",
    topic=topic,
    scope=scope,
)

context = ControlContext(
    session_id=None,
    topic=None,
    scope=None,
    status=None,
)

validated_command = (
    validator.validate(
        command=command,
        context=context,
    )
)


assert (
    validated_command.topic
    == topic
)

assert (
    validated_command.scope
    == scope
)


print(
    "Topic preserved: PASSED"
)

print(
    "Initial scope preserved: PASSED"
)


#
# -------------------------------------------------
# Execute through the real command handler and
# workflow service.
# -------------------------------------------------
#

print()
print("TEST 2 - WORKFLOW EXECUTION")
print("---------------------------")


result = handler.execute(
    validated_command
)


assert (
    fake_graph.state
    is not None
)


print(
    f"Session ID: {result.session_id}"
)

print(
    f"Result topic: {result.topic}"
)

print(
    f"Result status: {result.status}"
)


#
# -------------------------------------------------
# Verify graph state.
# -------------------------------------------------
#

print()
print("TEST 3 - GRAPH INITIAL STATE")
print("----------------------------")


assert (
    fake_graph.state["session_id"]
    == result.session_id
)

assert (
    fake_graph.state["topic"]
    == topic
)

assert (
    fake_graph.state["scope"]
    == scope
)

assert (
    fake_graph.state["resume"]
    is False
)

assert (
    fake_graph.state[
        "execution_target"
    ]
    == "complete"
)


print(
    "Session ID propagated: PASSED"
)

print(
    "Topic propagated: PASSED"
)

print(
    "Initial scope propagated: PASSED"
)

print(
    "New-workflow resume flag: PASSED"
)

print(
    "Complete execution target: PASSED"
)


#
# -------------------------------------------------
# Verify durable SQL state.
# -------------------------------------------------
#

print()
print("TEST 4 - SQL PERSISTENCE")
print("------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.get(
            result.session_id
        )
    )

    assert (
        research_session
        is not None
    )

    assert (
        research_session.topic
        == topic
    )

    assert (
        research_session.scope
        == scope
    )

    assert (
        research_session.status
        == "completed"
    )

    print(
        f"Persisted topic: "
        f"{research_session.topic}"
    )

    print(
        f"Persisted scope: "
        f"{research_session.scope}"
    )

    print(
        f"Persisted status: "
        f"{research_session.status}"
    )


print()
print(
    "Topic persisted: PASSED"
)

print(
    "Initial scope persisted: PASSED"
)

print(
    "Authoritative lifecycle status: PASSED"
)


#
# -------------------------------------------------
# Final command-handler result.
# -------------------------------------------------
#

print()
print("TEST 5 - COMMAND RESULT")
print("-----------------------")


assert (
    result.topic
    == topic
)

assert (
    result.status
    == "completed"
)


print(
    "ResearchExecutionResult topic: PASSED"
)

print(
    "ResearchExecutionResult status: PASSED"
)


print()
print("===========================")
print("PASS")
print("===========================")

print(
    "Initial research scope survives the "
    "complete deterministic start path."
)