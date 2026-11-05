from agents.control_agent import (
    ControlAgent,
)

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from config import settings

from control.start_research_command_handler import (
    StartResearchCommandHandler,
)

from domain.control import (
    ControlContext,
)

from models.factory import (
    ChatModelFactory,
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
print("CONTROL INITIAL SCOPE INTEGRATION TEST")
print("======================================")


class FakeGraph:

    def __init__(self):
        self.state = None

    def invoke(
        self,
        state,
    ):
        self.state = state

        #
        # Simulate successful workflow completion.
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
# Real Control Agent.
# -------------------------------------------------
#

model = ChatModelFactory.create(
    settings.controller_model
)

control_agent = ControlAgent(
    model=model
)

validator = ControlCommandValidator()


#
# -------------------------------------------------
# Real deterministic application path with fake
# graph execution.
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


#
# -------------------------------------------------
# User request.
# -------------------------------------------------
#

user_message = (
    "Research the effect of Bitcoin mining "
    "on energy systems, focusing specifically "
    "on electricity pricing, grid incentives, "
    "and renewable-energy investment."
)

context = ControlContext(
    session_id=None,
    topic=None,
    scope=None,
    status=None,
)


print()
print("USER REQUEST")
print("------------")

print(
    user_message
)


#
# -------------------------------------------------
# Real Qwen interpretation.
# -------------------------------------------------
#

print()
print("CONTROL AGENT")
print("-------------")


command = control_agent.interpret(
    user_message=user_message,
    context=context,
)


print(
    f"Operation:    {command.operation}"
)

print(
    f"Topic:        {command.topic}"
)

print(
    f"Scope:        {command.scope}"
)

print(
    f"Instructions: {command.instructions}"
)


#
# -------------------------------------------------
# Deterministic validation.
# -------------------------------------------------
#

print()
print("COMMAND VALIDATION")
print("------------------")


command = validator.validate(
    command=command,
    context=context,
)


assert (
    command.operation
    == "start_research"
)

assert command.topic

assert command.scope


scope_text = (
    command.scope.casefold()
)


assert (
    "electricity" in scope_text
)

assert (
    "grid" in scope_text
)

assert (
    "renewable" in scope_text
)


print(
    "Operation validation: PASSED"
)

print(
    "Topic validation: PASSED"
)

print(
    "Initial scope validation: PASSED"
)


#
# -------------------------------------------------
# Execute through handler/workflow/repository.
# -------------------------------------------------
#

print()
print("WORKFLOW")
print("--------")


result = handler.execute(
    command
)


print(
    f"Session ID: {result.session_id}"
)

print(
    f"Topic:      {result.topic}"
)

print(
    f"Status:     {result.status}"
)


#
# -------------------------------------------------
# Validate graph input.
# -------------------------------------------------
#

print()
print("GRAPH STATE")
print("-----------")


assert (
    fake_graph.state
    is not None
)

assert (
    fake_graph.state["session_id"]
    == result.session_id
)

assert (
    fake_graph.state["topic"]
    == command.topic
)

assert (
    fake_graph.state["scope"]
    == command.scope
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
    f"Topic:  "
    f"{fake_graph.state['topic']}"
)

print(
    f"Scope:  "
    f"{fake_graph.state['scope']}"
)


print()
print(
    "Control topic reached graph: PASSED"
)

print(
    "Control scope reached graph: PASSED"
)


#
# -------------------------------------------------
# Validate durable SQL state.
# -------------------------------------------------
#

print()
print("SQL")
print("---")


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
        == command.topic
    )

    assert (
        research_session.scope
        == command.scope
    )

    print(
        f"Persisted topic: "
        f"{research_session.topic}"
    )

    print(
        f"Persisted scope: "
        f"{research_session.scope}"
    )


print()
print(
    "Control topic persisted: PASSED"
)

print(
    "Control scope persisted: PASSED"
)


print()
print("======================================")
print("PASS")
print("======================================")

print(
    "Natural-language initial research scope "
    "survives the complete control-to-workflow "
    "integration path."
)