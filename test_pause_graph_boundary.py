from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from typing import (
    NotRequired,
    TypedDict,
)

from graph.research_graph import (
    route_pause,
)

from nodes.check_pause import (
    CheckPauseNode,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


print()
print("PAUSE GRAPH BOUNDARY TEST")
print("=========================")


#
# -------------------------------------------------
# Minimal graph state.
# -------------------------------------------------
#

class TestState(TypedDict):

    session_id: str

    pause_requested: NotRequired[bool]

    work_completed: NotRequired[bool]

    continuation_executed: NotRequired[bool]


#
# -------------------------------------------------
# Test nodes.
# -------------------------------------------------
#

def work_node(
    state: TestState,
) -> dict:

    return {
        "work_completed": True,
    }


def continuation_node(
    state: TestState,
) -> dict:

    return {
        "continuation_executed": True,
    }


#
# -------------------------------------------------
# Build a small graph using the production
# CheckPauseNode and production route_pause().
#
# work
#   ↓
# check_pause
#   ├── pause    → END
#   └── continue → continuation
# -------------------------------------------------
#

check_pause = CheckPauseNode(
    session_factory=SessionLocal,
)


builder = StateGraph(
    TestState
)

builder.add_node(
    "work",
    work_node,
)

builder.add_node(
    "check_pause",
    check_pause,
)

builder.add_node(
    "continuation",
    continuation_node,
)


builder.add_edge(
    START,
    "work",
)

builder.add_edge(
    "work",
    "check_pause",
)

builder.add_conditional_edges(
    "check_pause",
    route_pause,
    {
        "pause": END,
        "continue": "continuation",
    },
)

builder.add_edge(
    "continuation",
    END,
)


graph = builder.compile()


#
# -------------------------------------------------
# TEST 1
#
# No pause request:
#
# work → check_pause → continuation → END
# -------------------------------------------------
#

print()
print("TEST 1 - CONTINUE")
print("-----------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic=(
                "Pause graph boundary "
                "continue test"
            ),
        )
    )

    continue_session_id = (
        research_session.id
    )


result = graph.invoke(
    {
        "session_id":
            continue_session_id,
    }
)


assert (
    result["work_completed"]
    is True
)

assert (
    result["pause_requested"]
    is False
)

assert (
    result["continuation_executed"]
    is True
)


print(
    "Work executed: PASSED"
)

print(
    "Pause check returned False: PASSED"
)

print(
    "Continuation executed: PASSED"
)


#
# -------------------------------------------------
# TEST 2
#
# Pause requested before invocation:
#
# work → check_pause → END
#
# Work is allowed to finish because pause is only
# observed at the safe boundary.
# -------------------------------------------------
#

print()
print("TEST 2 - PAUSE AT BOUNDARY")
print("--------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic=(
                "Pause graph boundary "
                "pause test"
            ),
        )
    )

    pause_session_id = (
        research_session.id
    )

    repository.request_pause(
        pause_session_id
    )


result = graph.invoke(
    {
        "session_id":
            pause_session_id,
    }
)


assert (
    result["work_completed"]
    is True
)

assert (
    result["pause_requested"]
    is True
)

assert (
    result.get(
        "continuation_executed",
        False,
    )
    is False
)


print(
    "Current work completed: PASSED"
)

print(
    "Pause check returned True: PASSED"
)

print(
    "Continuation prevented: PASSED"
)


#
# -------------------------------------------------
# TEST 3
#
# CheckPauseNode must not consume the durable
# request when it ends the graph.
# -------------------------------------------------
#

print()
print("TEST 3 - PAUSE REMAINS DURABLE")
print("------------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    assert (
        repository.is_pause_requested(
            pause_session_id
        )
        is True
    )


print(
    "Pause request remains durable: PASSED"
)


print()
print("=========================")
print("PASS")
print("=========================")

print(
    "LangGraph cooperatively stops at the "
    "pause boundary without interrupting the "
    "current unit of work."
)