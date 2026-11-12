
from dataclasses import replace
from uuid import uuid4

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from graph.state import ResearchState

from nodes.select_review_question import (
    SelectReviewQuestionNode,
)

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
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
        "select_review_question",
        SelectReviewQuestionNode(
            session_factory=SessionLocal,
        ),
    )

    builder.add_edge(
        START,
        "select_review_question",
    )

    builder.add_edge(
        "select_review_question",
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
        },
        config={
            "configurable": configurable,
        },
    )


def expect_rejection(
    graph,
    session_id,
    lease,
    exception_type,
    protected_session_ids,
):

    before = {
        item: get_snapshot(item)
        for item in protected_session_ids
    }

    try:

        invoke_graph(
            graph,
            session_id,
            lease,
        )

    except exception_type:

        pass

    else:

        raise AssertionError(
            "Graph execution was unexpectedly accepted."
        )

    after = {
        item: get_snapshot(item)
        for item in protected_session_ids
    }

    assert after == before, (
        "Rejected graph execution changed "
        "review lifecycle persistence."
    )


def main():

    print()
    print("GRAPH REVIEW SELECTION LEASE")
    print("============================")

    sessions = []

    try:

        session_a = create_session()
        sessions.append(session_a)

        session_b = create_session()
        sessions.append(session_b)

        session_c = create_session()
        sessions.append(session_c)

        question_a1 = create_review_question(
            session_a,
            "researched",
        )

        question_a2 = create_review_question(
            session_a,
            "researched",
        )

        question_b = create_review_question(
            session_b,
            "reviewing",
        )

        create_review_question(
            session_c,
            "pending",
        )

        for session_id in sessions:

            set_session_status(
                session_id,
                "researching",
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

            lease_c = ExecutionLeaseRepository(
                db
            ).acquire(
                session_c
            )

        graph = create_graph()

        # Missing execution lease.

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

        # Execution lease belongs to
        # another session.

        expect_rejection(
            graph,
            session_a,
            lease_b,
            ValueError,
            [session_a, session_b],
        )

        print(
            "TEST 2 - Mismatched lease rejected: PASSED"
        )

        # Invalid lease owner.

        invalid_lease = replace(
            lease_a,
            owner=str(uuid4()),
        )

        expect_rejection(
            graph,
            session_a,
            invalid_lease,
            ExecutionLeaseFenceRejected,
            [session_a],
        )

        print(
            "TEST 3 - Invalid owner rejected: PASSED"
        )

        # Select first eligible question.

        result = invoke_graph(
            graph,
            session_a,
            lease_a,
        )

        assert result[
            "current_review_question_id"
        ] == question_a1

        assert result[
            "current_review_question"
        ] is not None

        assert get_snapshot(
            session_a
        ) == (
            "reviewing",
            (
                (question_a1, "reviewing"),
                (question_a2, "researched"),
            ),
        )

        print(
            "TEST 4 - First review question selected: PASSED"
        )

        # Retry recovers the same question.

        result = invoke_graph(
            graph,
            session_a,
            lease_a,
        )

        assert result[
            "current_review_question_id"
        ] == question_a1

        assert len(
            get_snapshot(session_a)[1]
        ) == 2

        print(
            "TEST 5 - Active review recovered: PASSED"
        )

        # An already reviewing question
        # is selected ahead of other work.

        result = invoke_graph(
            graph,
            session_b,
            lease_b,
        )

        assert result[
            "current_review_question_id"
        ] == question_b

        assert get_snapshot(
            session_b
        )[0] == "reviewing"

        print(
            "TEST 6 - Existing review recovered: PASSED"
        )

        # No eligible review question.

        before_c = get_snapshot(
            session_c
        )

        result = invoke_graph(
            graph,
            session_c,
            lease_c,
        )

        assert result[
            "current_review_question_id"
        ] is None

        assert result[
            "current_review_question"
        ] is None

        assert get_snapshot(
            session_c
        ) == before_c

        print(
            "TEST 7 - No eligible question: PASSED"
        )

        # Expired execution lease.

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
            "TEST 8 - Expired lease rejected: PASSED"
        )

        # A replacement lease supersedes
        # the previous execution.

        with SessionLocal() as db:

            replacement_lease_c = (
                ExecutionLeaseRepository(db)
                .acquire(
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
            "TEST 9 - Superseded lease rejected: PASSED"
        )

        # Valid replacement lease still
        # returns no eligible question.

        result = invoke_graph(
            graph,
            session_c,
            replacement_lease_c,
        )

        assert result[
            "current_review_question_id"
        ] is None

        assert get_snapshot(
            session_c
        ) == before_c

        print(
            "TEST 10 - Valid replacement lease: PASSED"
        )

        # Verify session isolation.

        assert get_snapshot(
            session_a
        ) == (
            "reviewing",
            (
                (question_a1, "reviewing"),
                (question_a2, "researched"),
            ),
        )

        assert get_snapshot(
            session_b
        ) == (
            "reviewing",
            (
                (question_b, "reviewing"),
            ),
        )

        print(
            "TEST 11 - Session isolation preserved: PASSED"
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
