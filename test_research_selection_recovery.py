
from uuid import uuid4

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from graph.state import (
    ResearchState,
)

from nodes.select_question import (
    SelectQuestionNode,
)

from nodes.check_existing_search import (
    CheckExistingSearchNode,
)

from persistence.database import (
    SessionLocal,
)

from persistence.models import (
    ResearchQuestion,
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
    create_review_question,
    set_session_status,
)

from sqlalchemy import inspect

from persistence.models import (
    ResearchQuestion,
    SearchAttempt,
)


def create_graph():

    builder = StateGraph(
        ResearchState
    )

    builder.add_node(
        "select_question",
        SelectQuestionNode(
            session_factory=SessionLocal,
        ),
    )

    builder.add_node(
        "check_existing_search",
        CheckExistingSearchNode(
            session_factory=SessionLocal,
        ),
    )

    builder.add_edge(
        START,
        "select_question",
    )

    builder.add_conditional_edges(
        "select_question",
        lambda state: (
            "finished"
            if state["current_question_id"] is None
            else "research"
        ),
        {
            "finished": END,
            "research": "check_existing_search",
        },
    )

    builder.add_edge(
        "check_existing_search",
        END,
    )

    return builder.compile()


def invoke_graph(
    graph,
    session_id,
    lease,
):

    return graph.invoke(
        {
            "session_id": session_id,
            "topic": "Research recovery test",
            "resume": True,
            "resume_phase": "planned",
            "execution_target": "research",
        },
        config={
            "configurable": {
                "execution_lease": lease,
            }
        },
    )


def get_question_status(
    question_id,
):

    with SessionLocal() as db:

        question = db.get(
            ResearchQuestion,
            question_id,
        )

        assert question is not None

        return question.status


def get_attempt_count(
    question_id: int,
) -> int:

    question_table = (
        ResearchQuestion.__table__
    )

    attempt_mapper = inspect(
        SearchAttempt
    )

    question_fk_columns = [
        column
        for column in attempt_mapper.columns
        if any(
            foreign_key.column.table
            is question_table
            for foreign_key in column.foreign_keys
        )
    ]

    if len(question_fk_columns) != 1:

        raise RuntimeError(
            "Expected exactly one foreign key "
            "from SearchAttempt to ResearchQuestion. "
            f"Found {len(question_fk_columns)}."
        )

    question_fk_column = (
        question_fk_columns[0]
    )

    with SessionLocal() as db:

        return (
            db.query(
                SearchAttempt
            )
            .filter(
                question_fk_column == question_id
            )
            .count()
        )



def expect_rejection(
    operation,
):

    try:

        operation()

    except Exception:

        return

    raise AssertionError(
        "Expected execution to be rejected."
    )


def main():

    print()
    print("DURABLE RESEARCH RECOVERY")
    print("=========================")

    session_id = create_session()

    try:

        set_session_status(
            session_id,
            "planned",
        )

        question_1 = create_review_question(
            session_id,
            status="researched",
        )

        question_2 = create_review_question(
            session_id,
            status="researching",
        )

        question_3 = create_review_question(
            session_id,
            status="pending",
        )

        lease = acquire_lease(
            session_id
        )

        graph = create_graph()

        #
        # Existing researched questions must
        # not be selected again.
        #

        result = invoke_graph(
            graph,
            session_id,
            lease,
        )

        assert (
            result["current_question_id"]
            == question_2
        )

        assert (
            get_question_status(
                question_1
            )
            == "researched"
        )

        print(
            "TEST 1 - Researched question skipped: PASSED"
        )

        #
        # An interrupted researching question
        # must be selected before pending work.
        #

        assert (
            get_question_status(
                question_2
            )
            == "researching"
        )

        assert (
            get_question_status(
                question_3
            )
            == "pending"
        )

        print(
            "TEST 2 - Active question prioritised: PASSED"
        )

        #
        # The initial search attempt must
        # have been created.
        #

        attempt_id = result[
            "current_search_attempt_id"
        ]

        assert attempt_id is not None

        assert result[
            "search_required"
        ] is True

        assert (
            get_attempt_count(
                question_2
            )
            == 1
        )

        print(
            "TEST 3 - Initial search attempt created: PASSED"
        )

        #
        # Repeating the graph invocation must
        # reuse the existing running attempt.
        #

        result = invoke_graph(
            graph,
            session_id,
            lease,
        )

        assert (
            result["current_question_id"]
            == question_2
        )

        assert (
            result["current_search_attempt_id"]
            == attempt_id
        )

        assert (
            get_attempt_count(
                question_2
            )
            == 1
        )

        print(
            "TEST 4 - Running attempt reused: PASSED"
        )

        #
        # Expired ownership must prevent
        # the graph from advancing.
        #

        expire_lease(
            session_id
        )

        before_count = get_attempt_count(
            question_2
        )

        expect_rejection(
            lambda: invoke_graph(
                graph,
                session_id,
                lease,
            )
        )

        assert (
            get_attempt_count(
                question_2
            )
            == before_count
        )

        print(
            "TEST 5 - Expired worker rejected: PASSED"
        )

        #
        # A replacement worker must recover
        # the same question and attempt.
        #

        replacement_lease = acquire_lease(
            session_id
        )

        result = invoke_graph(
            graph,
            session_id,
            replacement_lease,
        )

        assert (
            result["current_question_id"]
            == question_2
        )

        assert (
            result["current_search_attempt_id"]
            == attempt_id
        )

        assert (
            get_attempt_count(
                question_2
            )
            == 1
        )

        print(
            "TEST 6 - Replacement worker recovered attempt: PASSED"
        )

        #
        # Complete the recovered question.
        #

        from persistence.research_session_repository import (
            ResearchSessionRepository,
        )

        with SessionLocal() as db:

            ResearchSessionRepository(
                db
            ).set_question_status_fenced(
                session_id=session_id,
                question_id=question_2,
                status="researched",
                lease=replacement_lease,
            )

        result = invoke_graph(
            graph,
            session_id,
            replacement_lease,
        )

        assert (
            result["current_question_id"]
            == question_3
        )

        assert (
            get_question_status(
                question_3
            )
            == "researching"
        )

        print(
            "TEST 7 - Next pending question selected: PASSED"
        )

        #
        # Complete the final question.
        #

        with SessionLocal() as db:

            ResearchSessionRepository(
                db
            ).set_question_status_fenced(
                session_id=session_id,
                question_id=question_3,
                status="researched",
                lease=replacement_lease,
            )

        result = invoke_graph(
            graph,
            session_id,
            replacement_lease,
        )

        assert (
            result["current_question_id"]
            is None
        )

        assert (
            result["current_question"]
            is None
        )

        print(
            "TEST 8 - Exhausted question queue detected: PASSED"
        )

        print()
        print("PASS")

    finally:

        delete_session(
            session_id
        )


if __name__ == "__main__":

    main()
