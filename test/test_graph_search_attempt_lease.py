
from dataclasses import replace
from uuid import uuid4

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from graph.state import ResearchState

from nodes.check_existing_search import (
    CheckExistingSearchNode,
)

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from test_search_result_fencing import (
    create_session,
    create_question,
    delete_session,
)

from test_search_attempt_resolution_fencing import (
    create_attempt,
    get_attempts,
    set_attempt_status,
    set_question_pending,
)


def create_graph():

    builder = StateGraph(
        ResearchState
    )

    builder.add_node(
        "check_existing_search",
        CheckExistingSearchNode(
            session_factory=SessionLocal,
        ),
    )

    builder.add_edge(
        START,
        "check_existing_search",
    )

    builder.add_edge(
        "check_existing_search",
        END,
    )

    return builder.compile()


def invoke_graph(
    graph,
    session_id,
    question_id,
    lease=None,
):

    configurable = {}

    if lease is not None:

        configurable["execution_lease"] = lease

    return graph.invoke(
        {
            "session_id": session_id,
            "current_question_id": question_id,
        },
        config={
            "configurable": configurable,
        },
    )


def expect_rejection(
    graph,
    session_id,
    question_id,
    lease,
    exception_type,
    protected_question_ids,
):

    before = {
        question_id: get_attempts(question_id)
        for question_id in protected_question_ids
    }

    try:

        invoke_graph(
            graph,
            session_id,
            question_id,
            lease,
        )

    except exception_type:

        pass

    else:

        raise AssertionError(
            "Graph execution was unexpectedly accepted."
        )

    after = {
        question_id: get_attempts(question_id)
        for question_id in protected_question_ids
    }

    assert after == before, (
        "Rejected graph execution changed "
        "search attempt persistence."
    )


def main():

    print()
    print("GRAPH SEARCH ATTEMPT LEASE")
    print("==========================")

    sessions = []

    try:

        session_a = create_session()
        sessions.append(session_a)

        session_b = create_session()
        sessions.append(session_b)

        question_a = create_question(
            session_a
        )

        question_b = create_question(
            session_b
        )

        set_question_pending(
            question_a
        )

        set_question_pending(
            question_b
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

        # Missing lease.

        expect_rejection(
            graph,
            session_a,
            question_a,
            None,
            RuntimeError,
            [question_a],
        )

        print(
            "TEST 1 - Missing lease rejected: PASSED"
        )

        # Mismatched session lease.

        expect_rejection(
            graph,
            session_b,
            question_b,
            lease_a,
            ValueError,
            [question_b],
        )

        print(
            "TEST 2 - Mismatched lease rejected: PASSED"
        )

        # Invalid owner.

        invalid_lease = replace(
            lease_a,
            owner=str(uuid4()),
        )

        expect_rejection(
            graph,
            session_a,
            question_a,
            invalid_lease,
            ExecutionLeaseFenceRejected,
            [question_a],
        )

        print(
            "TEST 3 - Invalid owner rejected: PASSED"
        )

        # A new question creates one running attempt.

        result = invoke_graph(
            graph,
            session_a,
            question_a,
            lease_a,
        )

        assert result["search_required"] is True

        attempt_a = result[
            "current_search_attempt_id"
        ]

        assert attempt_a is not None

        attempts = get_attempts(
            question_a
        )

        assert len(attempts) == 1
        assert attempts[0][0] == attempt_a
        assert attempts[0][3] == "running"

        print(
            "TEST 4 - Initial attempt created: PASSED"
        )

        # Repeated graph execution resumes
        # the same attempt.

        result = invoke_graph(
            graph,
            session_a,
            question_a,
            lease_a,
        )

        assert result["search_required"] is True

        assert result[
            "current_search_attempt_id"
        ] == attempt_a

        assert len(
            get_attempts(question_a)
        ) == 1

        print(
            "TEST 5 - Running attempt resumed: PASSED"
        )

        # An existing pending attempt is resumed.

        attempt_b = create_attempt(
            session_b,
            question_b,
        )

        result = invoke_graph(
            graph,
            session_b,
            question_b,
            lease_b,
        )

        assert result["search_required"] is True

        assert result[
            "current_search_attempt_id"
        ] == attempt_b

        assert get_attempts(
            question_b
        )[0][3] == "running"

        print(
            "TEST 6 - Pending attempt resumed: PASSED"
        )

        # A completed attempt means the
        # question needs no further search.

        set_attempt_status(
            attempt_a,
            "completed",
        )

        result = invoke_graph(
            graph,
            session_a,
            question_a,
            lease_a,
        )

        assert result["search_required"] is False

        assert result[
            "current_search_attempt_id"
        ] is None

        assert len(
            get_attempts(question_a)
        ) == 1

        print(
            "TEST 7 - Completed history skips search: PASSED"
        )

        # A valid lease cannot operate on a
        # question belonging to another session.

        expect_rejection(
            graph,
            session_a,
            question_b,
            lease_a,
            ValueError,
            [
                question_a,
                question_b,
            ],
        )

        print(
            "TEST 8 - Cross-session question rejected: PASSED"
        )

        # Confirm that the other session's
        # running attempt remains unchanged.

        attempts_b = get_attempts(
            question_b
        )

        assert len(attempts_b) == 1
        assert attempts_b[0][0] == attempt_b
        assert attempts_b[0][3] == "running"

        print(
            "TEST 9 - Other session unchanged: PASSED"
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
