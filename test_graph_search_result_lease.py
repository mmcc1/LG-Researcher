
from dataclasses import replace
from uuid import uuid4

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from graph.state import ResearchState

from nodes.save_search_results import (
    SaveSearchResultsNode,
)

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from test_search_result_fencing import (
    create_session,
    create_question,
    create_running_attempt,
    make_results,
    get_snapshot,
    delete_session,
)


def create_graph():

    builder = StateGraph(
        ResearchState
    )

    builder.add_node(
        "save_search_results",
        SaveSearchResultsNode(
            session_factory=SessionLocal,
        ),
    )

    builder.add_edge(
        START,
        "save_search_results",
    )

    builder.add_edge(
        "save_search_results",
        END,
    )

    return builder.compile()


def make_state(
    session_id,
    question_id,
    attempt_id,
):

    return {
        "session_id": session_id,
        "current_question_id": question_id,
        "current_search_attempt_id": attempt_id,
        "search_results": make_results(),
    }


def invoke_graph(
    graph,
    state,
    lease=None,
):

    configurable = {}

    if lease is not None:

        configurable["execution_lease"] = lease

    return graph.invoke(
        state,
        config={
            "configurable": configurable,
        },
    )


def expect_rejection(
    graph,
    state,
    lease,
    exception_type,
):

    attempt_id = state[
        "current_search_attempt_id"
    ]

    before = get_snapshot(
        attempt_id
    )

    try:

        invoke_graph(
            graph,
            state,
            lease,
        )

    except exception_type:

        pass

    else:

        raise AssertionError(
            "Graph execution was unexpectedly accepted."
        )

    after = get_snapshot(
        attempt_id
    )

    assert after == before, (
        "Rejected graph execution changed "
        "the search attempt."
    )


def main():

    print()
    print("GRAPH SEARCH RESULT LEASE")
    print("=========================")

    session_a = create_session()
    session_b = create_session()

    try:

        question_a = create_question(
            session_a
        )

        question_b = create_question(
            session_b
        )

        attempt_a = create_running_attempt(
            session_a,
            question_a,
        )

        attempt_b = create_running_attempt(
            session_b,
            question_b,
        )

        with SessionLocal() as db:

            lease_a = ExecutionLeaseRepository(
                db
            ).acquire(
                session_a
            )

            lease_b = ExecutionLeaseRepository(
                db
            ).acquire(
                session_b
            )

        graph = create_graph()

        state_a = make_state(
            session_a,
            question_a,
            attempt_a,
        )

        state_b = make_state(
            session_b,
            question_b,
            attempt_b,
        )

        # Missing lease must be rejected.

        expect_rejection(
            graph,
            state_a,
            None,
            RuntimeError,
        )

        print(
            "TEST 1 - Missing lease rejected: PASSED"
        )

        # A lease for another session must fail.

        expect_rejection(
            graph,
            state_b,
            lease_a,
            ValueError,
        )

        print(
            "TEST 2 - Mismatched lease rejected: PASSED"
        )

        # A forged owner must fail the SQL fence.

        invalid_lease = replace(
            lease_a,
            owner=str(uuid4()),
        )

        expect_rejection(
            graph,
            state_a,
            invalid_lease,
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 3 - Invalid owner rejected: PASSED"
        )

        # Valid execution through LangGraph.

        invoke_graph(
            graph,
            state_a,
            lease_a,
        )

        status, completed_at, results = (
            get_snapshot(
                attempt_a
            )
        )

        assert status == "completed"
        assert completed_at is not None
        assert len(results) == 2

        print(
            "TEST 4 - Graph persistence completed: PASSED"
        )

        # Repeating the same graph operation
        # must not create duplicate results.

        before = get_snapshot(
            attempt_a
        )

        invoke_graph(
            graph,
            state_a,
            lease_a,
        )

        assert get_snapshot(attempt_a) == before

        print(
            "TEST 5 - Graph retry idempotent: PASSED"
        )

        # Verify that the other attempt was
        # not modified by any execution.

        status, completed_at, results = (
            get_snapshot(
                attempt_b
            )
        )

        assert status == "running"
        assert completed_at is None
        assert len(results) == 0

        print(
            "TEST 6 - Other attempt unchanged: PASSED"
        )

        print()
        print("PASS")

    finally:

        delete_session(
            session_b
        )

        delete_session(
            session_a
        )


if __name__ == "__main__":

    main()
