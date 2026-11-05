from application.research_workflow_service import (
    ResearchWorkflowService,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


print()
print("WORKFLOW SCOPE STATE TEST")
print("=========================")


class FakeGraph:

    def __init__(self):
        self.state = None

    def invoke(
        self,
        state,
    ):
        self.state = state

        return state


#
# -------------------------------------------------
# Create a real SQL research session.
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


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic=topic
        )
    )

    session_id = (
        research_session.id
    )

    #
    # Put the session into a resumable research
    # lifecycle state.
    #

    repository.set_status(
        session_id,
        "researching",
    )

    repository.set_scope(
        session_id=session_id,
        scope=scope,
    )


print(
    f"Test session: {session_id}"
)


#
# -------------------------------------------------
# Resume through the real workflow service, but
# replace LangGraph with a fake graph so nothing
# beyond state construction executes.
# -------------------------------------------------
#

fake_graph = FakeGraph()

workflow_service = (
    ResearchWorkflowService(
        graph=fake_graph,
        session_factory=SessionLocal,
    )
)


result = (
    workflow_service.resume_research(
        session_id
    )
)


#
# -------------------------------------------------
# Validate the graph input.
# -------------------------------------------------
#

assert fake_graph.state is not None


print()
print("GRAPH INITIAL STATE")
print("-------------------")

print(
    f"Session ID: "
    f"{fake_graph.state['session_id']}"
)

print(
    f"Topic:      "
    f"{fake_graph.state['topic']}"
)

print(
    f"Scope:      "
    f"{fake_graph.state['scope']}"
)

print(
    f"Resume:     "
    f"{fake_graph.state['resume']}"
)

print(
    f"Target:     "
    f"{fake_graph.state['execution_target']}"
)


assert (
    fake_graph.state["session_id"]
    == session_id
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
    is True
)

assert (
    fake_graph.state[
        "execution_target"
    ]
    == "research"
)


assert (
    result.session_id
    == session_id
)

assert (
    result.topic
    == topic
)


print()
print(
    "Persisted topic loaded: PASSED"
)

print(
    "Persisted scope loaded: PASSED"
)

print(
    "Scope placed in graph state: PASSED"
)

print(
    "Resume flag preserved: PASSED"
)

print(
    "Research execution target preserved: PASSED"
)


print()
print("=========================")
print("PASS")
print("=========================")

print(
    "ResearchWorkflowService correctly "
    "propagates durable research scope "
    "into graph execution state."
)