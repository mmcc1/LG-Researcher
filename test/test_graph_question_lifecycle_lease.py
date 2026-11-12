
from dataclasses import replace
from uuid import uuid4

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from graph.state import ResearchState

from nodes.select_question import (
    SelectQuestionNode,
)

from nodes.complete_question import (
    CompleteQuestionNode,
)

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import ResearchQuestion

from test_search_result_fencing import (
    create_session,
    create_question,
    delete_session,
)


def create_graph(
    node_name,
    node,
):

    builder = StateGraph(
        ResearchState
    )

    builder.add_node(
        node_name,
        node,
    )

    builder.add_edge(
        START,
        node_name,
    )

    builder.add_edge(
        node_name,
        END,
    )

    return builder.compile()


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


def get_status(
    question_id,
):

    with SessionLocal() as db:

        question = db.get(
            ResearchQuestion,
            question_id,
        )

        assert question is not None

        return question.status


def set_pending(
    question_id,
):

    with SessionLocal() as db:

        question = db.get(
            ResearchQuestion,
            question_id,
        )

        assert question is not None

        question.status = "pending"

        db.commit()


def expect_rejection(
    graph,
    state,
    lease,
    exception_type,
    question_ids,
):

    before = {
        question_id: get_status(question_id)
        for question_id in question_ids
    }

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

    after = {
        question_id: get_status(question_id)
        for question_id in question_ids
    }

    assert after == before, (
        "Rejected execution changed question status."
    )


def main():

    print()
    print("GRAPH QUESTION LIFECYCLE LEASE")
    print("==============================")

    session_a = create_session()
    session_b = create_session()

    try:

        question_a = create_question(
            session_a
        )

        question_b = create_question(
            session_b
        )

        set_pending(
            question_a
        )

        set_pending(
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

        selection_graph = create_graph(
            "select_question",
            SelectQuestionNode(
                session_factory=SessionLocal,
            ),
        )

        completion_graph = create_graph(
            "complete_question",
            CompleteQuestionNode(
                session_factory=SessionLocal,
            ),
        )

        state_a = {
            "session_id": session_a,
        }

        state_b = {
            "session_id": session_b,
        }

        # Missing lease.

        expect_rejection(
            selection_graph,
            state_a,
            None,
            RuntimeError,
            [question_a],
        )

        print(
            "TEST 1 - Missing selection lease rejected: PASSED"
        )

        # Mismatched session lease.

        expect_rejection(
            selection_graph,
            state_b,
            lease_a,
            ValueError,
            [question_b],
        )

        print(
            "TEST 2 - Mismatched selection lease rejected: PASSED"
        )

        # Invalid owner.

        invalid_lease = replace(
            lease_a,
            owner=str(uuid4()),
        )

        expect_rejection(
            selection_graph,
            state_a,
            invalid_lease,
            ExecutionLeaseFenceRejected,
            [question_a],
        )

        print(
            "TEST 3 - Invalid selection owner rejected: PASSED"
        )

        # Valid selection.

        selected = invoke_graph(
            selection_graph,
            state_a,
            lease_a,
        )

        assert selected[
            "current_question_id"
        ] == question_a

        assert get_status(
            question_a
        ) == "researching"

        print(
            "TEST 4 - Graph selection completed: PASSED"
        )

        # Resume existing question.

        resumed = invoke_graph(
            selection_graph,
            state_a,
            lease_a,
        )

        assert resumed[
            "current_question_id"
        ] == question_a

        assert get_status(
            question_a
        ) == "researching"

        print(
            "TEST 5 - Graph selection resumes: PASSED"
        )

        completion_state = {
            "session_id": session_a,
            "current_question_id": question_a,
        }

        # Missing completion lease.

        expect_rejection(
            completion_graph,
            completion_state,
            None,
            RuntimeError,
            [question_a],
        )

        print(
            "TEST 6 - Missing completion lease rejected: PASSED"
        )

        # Invalid completion lease.

        expect_rejection(
            completion_graph,
            completion_state,
            invalid_lease,
            ExecutionLeaseFenceRejected,
            [question_a],
        )

        print(
            "TEST 7 - Invalid completion owner rejected: PASSED"
        )

        # Cross-session question.

        expect_rejection(
            completion_graph,
            {
                "session_id": session_b,
                "current_question_id": question_a,
            },
            lease_b,
            ValueError,
            [question_a, question_b],
        )

        print(
            "TEST 8 - Cross-session completion rejected: PASSED"
        )

        # Valid completion.

        invoke_graph(
            completion_graph,
            completion_state,
            lease_a,
        )

        assert get_status(
            question_a
        ) == "researched"

        print(
            "TEST 9 - Graph completion succeeded: PASSED"
        )

        # Idempotent completion.

        invoke_graph(
            completion_graph,
            completion_state,
            lease_a,
        )

        assert get_status(
            question_a
        ) == "researched"

        print(
            "TEST 10 - Graph completion retry unchanged: PASSED"
        )

        # No remaining question.

        finished = invoke_graph(
            selection_graph,
            state_a,
            lease_a,
        )

        assert finished[
            "current_question_id"
        ] is None

        print(
            "TEST 11 - No remaining question: PASSED"
        )

        # Other session remains untouched.

        assert get_status(
            question_b
        ) == "pending"

        print(
            "TEST 12 - Other session unchanged: PASSED"
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
