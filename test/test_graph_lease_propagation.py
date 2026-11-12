
from langgraph.graph import (
    START,
    StateGraph,
)

from langchain_core.runnables import RunnableConfig

from graph.state import ResearchState

from persistence.execution_lease_repository import (
    ExecutionLease,
)

from datetime import datetime, timezone


class LeaseProbeNode:

    def __call__(
        self,
        state: ResearchState,
        config: RunnableConfig,
    ) -> dict:

        lease = config.get(
            "configurable",
            {},
        ).get(
            "execution_lease"
        )

        assert isinstance(
            lease,
            ExecutionLease,
        )

        assert lease.session_id == state["session_id"]

        assert lease.owner == "test-owner"

        assert lease.version == 7

        return {}


def main():

    builder = StateGraph(
        ResearchState
    )

    builder.add_node(
        "lease_probe",
        LeaseProbeNode(),
    )

    builder.add_edge(
        START,
        "lease_probe",
    )

    graph = builder.compile()

    lease = ExecutionLease(
        session_id="test-session",
        owner="test-owner",
        version=7,
        expires_at=datetime.now(timezone.utc),
    )

    initial_state = {
        "session_id": "test-session",
        "topic": "Lease propagation test",
        "scope": None,
        "resume": False,
        "resume_phase": None,
        "execution_target": "research",
        "pause_requested": False,
        "research_plan": None,
        "current_question_id": None,
        "current_question": None,
        "search_required": False,
        "current_search_attempt_id": None,
        "search_plan": None,
        "search_results": [],
        "current_review_question_id": None,
        "current_review_question": None,
    }

    graph.invoke(
        initial_state,
        config={
            "configurable": {
                "execution_lease": lease,
            },
        },
    )

    print(
        "TEST 1 - Execution lease received by graph node: PASSED"
    )

    print()
    print("PASS")


if __name__ == "__main__":

    main()
