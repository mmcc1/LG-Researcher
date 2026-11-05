
from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from graph.state import ResearchState

from nodes.complete_review import (
    CompleteReviewNode,
)

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseFenceRejected,
)

from test_search_result_fencing import (
    create_session,
    delete_session,
    expire_lease,
)

from test_review_selection_fencing import (
    create_review_question,
    get_snapshot,
    set_session_status,
)


def create_graph():

    builder = StateGraph(
        ResearchState
    )

    builder.add_node(
        "complete_review",
        CompleteReviewNode(
            session_factory=SessionLocal,
        ),
    )

    builder.add_edge(
        START,
        "complete_review",
    )

    builder.add_edge(
        "complete_review",
        END,
    )

    return builder.compile()


def acquire_lease(
    session_id: str,
):

    with SessionLocal() as db:

        return ExecutionLeaseRepository(
            db
        ).acquire(
            session_id
        )


def invoke_graph(
    graph,
    session_id,
    lease=None,
):

    configurable = {}

    if lease is not None:

        configurable[
            "execution_lease"
        ] = lease

    return graph.invoke(
        {
            "session_id": session_id,
        },
        config={
            "configurable": configurable,
        },
    )


def expect_rejection(
    graph,
    session_id,
    lease,
    expected_exception,
    protected_sessions,
):

    before = {
        item: get_snapshot(item)
        for item in protected_sessions
    }

    try:

        invoke_graph(
            graph,
            session_id,
            lease,
        )

    except expected_exception:

        pass

    else:

        raise AssertionError(
            "Graph execution was "
            "unexpectedly accepted."
        )

    after = {
        item: get_snapshot(item)
        for item in protected_sessions
    }

    assert after == before, (
        "Rejected graph execution changed "
        "persisted research state."
    )


def main():

    print()
    print("GRAPH REVIEW COMPLETION")
    print("=======================")

    sessions = []

    try:

        session_a = create_session()
        sessions.append(session_a)

        session_b = create_session()
        sessions.append(session_b)

        session_c = create_session()
        sessions.append(session_c)

        for session_id in sessions:

            set_session_status(
                session_id,
                "researched",
            )

        create_review_question(
            session_a,
            "reviewed",
        )

        create_review_question(
            session_b,
            "researched",
        )

        create_review_question(
            session_c,
            "reviewed",
        )

        lease_a = acquire_lease(
            session_a
        )

        lease_b = acquire_lease(
            session_b
        )

        lease_c = acquire_lease(
            session_c
        )

        graph = create_graph()

        # Missing lease.

        expect_rejection(
            graph,
            session_a,
            None,
            RuntimeError,
            [session_a],
        )

        print(
            "TEST 1 - Missing lease rejected: PASSED"
        )

        # Successful completion.

        invoke_graph(
            graph,
            session_a,
            lease_a,
        )

        assert get_snapshot(
            session_a
        )[0] == "reviewed"

        print(
            "TEST 2 - Graph completion persisted: PASSED"
        )

        # Idempotent retry.

        before = get_snapshot(
            session_a
        )

        invoke_graph(
            graph,
            session_a,
            lease_a,
        )

        assert get_snapshot(
            session_a
        ) == before

        print(
            "TEST 3 - Graph retry idempotent: PASSED"
        )

        # Incomplete review.

        expect_rejection(
            graph,
            session_b,
            lease_b,
            ValueError,
            [session_b],
        )

        print(
            "TEST 4 - Incomplete review rejected: PASSED"
        )

        # Expired lease.

        expire_lease(
            session_c
        )

        expect_rejection(
            graph,
            session_c,
            lease_c,
            ExecutionLeaseFenceRejected,
            [session_c],
        )

        print(
            "TEST 5 - Expired lease rejected: PASSED"
        )

        # Replacement lease.

        replacement_lease_c = (
            acquire_lease(
                session_c
            )
        )

        expect_rejection(
            graph,
            session_c,
            lease_c,
            ExecutionLeaseFenceRejected,
            [session_c],
        )

        print(
            "TEST 6 - Superseded lease rejected: PASSED"
        )

        invoke_graph(
            graph,
            session_c,
            replacement_lease_c,
        )

        assert get_snapshot(
            session_c
        )[0] == "reviewed"

        print(
            "TEST 7 - Replacement lease succeeds: PASSED"
        )

        # Cross-session lease.

        expect_rejection(
            graph,
            session_b,
            lease_a,
            ValueError,
            [session_a, session_b],
        )

        print(
            "TEST 8 - Cross-session lease rejected: PASSED"
        )

        # Isolation.

        assert get_snapshot(
            session_b
        )[0] == "researched"

        print(
            "TEST 9 - Session isolation preserved: PASSED"
        )

        print()
        print("PASS")

    finally:

        for session_id in reversed(
            sessions
        ):

            delete_session(
                session_id
            )


if __name__ == "__main__":

    main()
