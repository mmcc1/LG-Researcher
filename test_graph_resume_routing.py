
from dataclasses import dataclass

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from graph.state import (
    ResearchState,
)

from graph.research_graph import (
    route_start,
    route_resume_phase,
)

from nodes.select_resume_phase import (
    SelectResumePhaseNode,
)

from persistence.database import (
    SessionLocal,
)

from test_search_result_fencing import (
    create_session,
    delete_session,
    expire_lease,
)

from test_review_completion_fencing import (
    acquire_lease,
)

from test_review_selection_fencing import (
    set_session_status,
)


@dataclass
class RouteObservation:

    destination: str | None = None

    invocations: int = 0


def create_graph(
    observation,
):

    builder = StateGraph(
        ResearchState
    )

    def record(
        destination,
    ):

        def handler(
            state,
        ):

            observation.destination = (
                destination
            )

            observation.invocations += 1

            return {}

        return handler

    builder.add_node(
        "select_resume_phase",
        SelectResumePhaseNode(
            session_factory=SessionLocal,
        ),
    )

    destinations = {
        "planning": "plan_research",
        "research": "select_question",
        "review": "select_review_question",
        "report": "generate_report",
        "finished": "finished",
    }

    for destination, node_name in (
        destinations.items()
    ):

        builder.add_node(
            node_name,
            record(
                destination
            ),
        )

        builder.add_edge(
            node_name,
            END,
        )

    builder.add_conditional_edges(
        START,
        route_start,
        {
            "new": "plan_research",
            "resume": "select_resume_phase",
        },
    )

    builder.add_conditional_edges(
        "select_resume_phase",
        route_resume_phase,
        destinations,
    )

    return builder.compile()


def invoke_graph(
    graph,
    session_id,
    lease,
    execution_target="complete",
    resume=True,
):

    return graph.invoke(
        {
            "session_id": session_id,
            "topic": "Resume routing test",
            "resume": resume,
            "resume_phase": None,
            "execution_target": (
                execution_target
            ),
        },
        config={
            "configurable": {
                "execution_lease": lease,
            }
        },
    )


def assert_route(
    graph,
    observation,
    session_id,
    lease,
    status,
    execution_target,
    expected_destination,
):

    set_session_status(
        session_id,
        status,
    )

    observation.destination = None

    before = observation.invocations

    result = invoke_graph(
        graph,
        session_id,
        lease,
        execution_target=execution_target,
    )

    assert (
        observation.destination
        == expected_destination
    ), (
        f"Status {status}, target "
        f"{execution_target}: expected "
        f"{expected_destination}, got "
        f"{observation.destination}"
    )

    assert (
        observation.invocations
        == before + 1
    )

    assert (
        result["resume_phase"]
        == status
    )


def main():

    print()
    print("LANGGRAPH RESUME ROUTING")
    print("========================")

    session_id = create_session()

    try:

        lease = acquire_lease(
            session_id
        )

        observation = RouteObservation()

        graph = create_graph(
            observation
        )

        complete_routes = [
            ("created", "planning"),
            ("planning", "planning"),
            ("planned", "research"),
            ("researching", "research"),
            ("researched", "review"),
            ("reviewing", "review"),
            ("reviewed", "report"),
            ("reporting", "report"),
            ("completed", "finished"),
        ]

        for status, destination in (
            complete_routes
        ):

            assert_route(
                graph,
                observation,
                session_id,
                lease,
                status,
                "complete",
                destination,
            )

            print(
                f"Complete target: "
                f"{status} -> "
                f"{destination}: PASSED"
            )

        research_routes = [
            ("created", "planning"),
            ("planning", "planning"),
            ("planned", "research"),
            ("researching", "research"),
            ("researched", "finished"),
            ("reviewing", "finished"),
            ("reviewed", "finished"),
            ("reporting", "finished"),
            ("completed", "finished"),
        ]

        for status, destination in (
            research_routes
        ):

            assert_route(
                graph,
                observation,
                session_id,
                lease,
                status,
                "research",
                destination,
            )

            print(
                f"Research target: "
                f"{status} -> "
                f"{destination}: PASSED"
            )

        observation.destination = None

        before = observation.invocations

        invoke_graph(
            graph,
            session_id,
            lease,
            execution_target="complete",
            resume=False,
        )

        assert (
            observation.destination
            == "planning"
        )

        assert (
            observation.invocations
            == before + 1
        )

        print(
            "Fresh execution starts planning: PASSED"
        )

        expire_lease(
            session_id
        )

        before = observation.invocations

        try:

            invoke_graph(
                graph,
                session_id,
                lease,
            )

        except Exception:

            pass

        else:

            raise AssertionError(
                "Expired lease was accepted."
            )

        assert (
            observation.invocations
            == before
        )

        print(
            "Expired lease prevents routing: PASSED"
        )

        print()
        print("PASS")

    finally:

        delete_session(
            session_id
        )


if __name__ == "__main__":

    main()
