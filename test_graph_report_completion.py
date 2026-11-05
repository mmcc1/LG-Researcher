
from dataclasses import replace
from uuid import uuid4

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from graph.state import (
    ResearchState,
)

from nodes.complete_report import (
    CompleteReportNode,
)

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
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
    get_snapshot,
    set_session_status,
)

from test_report_persistence_fencing import (
    delete_report,
    make_report,
    persist_report,
)


def create_graph():

    builder = StateGraph(
        ResearchState
    )

    builder.add_node(
        "complete_report",
        CompleteReportNode(
            session_factory=SessionLocal,
        ),
    )

    builder.add_edge(
        START,
        "complete_report",
    )

    builder.add_edge(
        "complete_report",
        END,
    )

    return builder.compile()


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
            "topic": "Graph completion verification",
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
            "Graph completion was "
            "unexpectedly accepted."
        )

    after = {
        item: get_snapshot(item)
        for item in protected_sessions
    }

    assert after == before, (
        "Rejected graph completion "
        "modified research session state."
    )


def main():

    print()
    print("GRAPH REPORT COMPLETION")
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
                "reporting",
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

        #
        # Create durable reports for two
        # sessions. Leave the third without
        # a report.
        #

        persist_report(
            session_a,
            make_report(),
            lease_a,
        )

        persist_report(
            session_b,
            make_report(),
            lease_b,
        )

        graph = create_graph()

        #
        # Successful graph completion.
        #

        invoke_graph(
            graph,
            session_a,
            lease_a,
        )

        assert get_snapshot(
            session_a
        )[0] == "completed"

        print(
            "TEST 1 - Graph completion persisted: PASSED"
        )

        #
        # Repeating the graph with the same
        # valid lease must be idempotent.
        #

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
            "TEST 2 - Graph completion idempotent: PASSED"
        )

        #
        # Missing execution lease.
        #

        expect_rejection(
            graph,
            session_b,
            None,
            RuntimeError,
            [session_a, session_b],
        )

        print(
            "TEST 3 - Missing graph lease rejected: PASSED"
        )

        #
        # Cross-session execution lease.
        #

        expect_rejection(
            graph,
            session_b,
            lease_a,
            ValueError,
            [session_a, session_b],
        )

        print(
            "TEST 4 - Cross-session lease rejected: PASSED"
        )

        #
        # Incorrect execution owner.
        #

        invalid_lease = replace(
            lease_b,
            owner=str(uuid4()),
        )

        expect_rejection(
            graph,
            session_b,
            invalid_lease,
            ExecutionLeaseFenceRejected,
            [session_b],
        )

        print(
            "TEST 5 - Incorrect owner rejected: PASSED"
        )

        #
        # Expire the current worker's lease.
        #

        expire_lease(
            session_b
        )

        expect_rejection(
            graph,
            session_b,
            lease_b,
            ExecutionLeaseFenceRejected,
            [session_b],
        )

        print(
            "TEST 6 - Expired worker rejected: PASSED"
        )

        #
        # A replacement worker acquires
        # execution ownership.
        #

        replacement_lease = (
            acquire_lease(
                session_b
            )
        )

        assert (
            replacement_lease.version
            > lease_b.version
        )

        expect_rejection(
            graph,
            session_b,
            lease_b,
            ExecutionLeaseFenceRejected,
            [session_b],
        )

        print(
            "TEST 7 - Superseded worker rejected: PASSED"
        )

        #
        # Replacement worker completes
        # the existing durable report.
        #

        invoke_graph(
            graph,
            session_b,
            replacement_lease,
        )

        assert get_snapshot(
            session_b
        )[0] == "completed"

        print(
            "TEST 8 - Replacement worker completes: PASSED"
        )

        #
        # Old worker cannot successfully
        # retry after completion.
        #

        expect_rejection(
            graph,
            session_b,
            lease_b,
            ExecutionLeaseFenceRejected,
            [session_b],
        )

        print(
            "TEST 9 - Stale completion retry rejected: PASSED"
        )

        #
        # A session without a durable
        # report must not complete.
        #

        expect_rejection(
            graph,
            session_c,
            lease_c,
            RuntimeError,
            [session_c],
        )

        print(
            "TEST 10 - Missing durable report rejected: PASSED"
        )

        #
        # Invalid lifecycle transition.
        #

        set_session_status(
            session_c,
            "reviewed",
        )

        expect_rejection(
            graph,
            session_c,
            lease_c,
            ValueError,
            [session_c],
        )

        print(
            "TEST 11 - Invalid lifecycle rejected: PASSED"
        )

        #
        # Verify isolation between all
        # three research sessions.
        #

        assert get_snapshot(
            session_a
        )[0] == "completed"

        assert get_snapshot(
            session_b
        )[0] == "completed"

        assert get_snapshot(
            session_c
        )[0] == "reviewed"

        print(
            "TEST 12 - Session isolation preserved: PASSED"
        )

        print()
        print("PASS")

    finally:

        for session_id in reversed(
            sessions
        ):

            delete_report(
                session_id
            )

            delete_session(
                session_id
            )


if __name__ == "__main__":

    main()
