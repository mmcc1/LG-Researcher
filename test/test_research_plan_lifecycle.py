
from dataclasses import replace
from uuid import uuid4

from sqlalchemy import text

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
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

# Adjust this import to the module containing
# your Pydantic research planning models.
from domain.research_plan import (
    ResearchPlan,
    ResearchQuestionPlan,
)


def make_plan():

    return ResearchPlan(
        topic="Quantum computing and Bitcoin",
        questions=[
            ResearchQuestionPlan(
                category="cryptography",
                question=(
                    "How could quantum computing "
                    "affect Bitcoin signatures?"
                ),
                rationale=(
                    "Establish the cryptographic "
                    "security implications."
                ),
            ),
            ResearchQuestionPlan(
                category="migration",
                question=(
                    "How could Bitcoin migrate "
                    "to quantum-resistant signatures?"
                ),
                rationale=(
                    "Identify potential mitigation "
                    "strategies."
                ),
            ),
        ],
    )


def prepare_execution(
    session_id,
    lease,
    resume=False,
):

    with SessionLocal() as db:

        return ResearchSessionRepository(
            db
        ).prepare_execution_fenced(
            session_id=session_id,
            lease=lease,
            resume=resume,
        )


def save_plan(
    session_id,
    plan,
    lease,
):

    with SessionLocal() as db:

        ResearchSessionRepository(
            db
        ).save_plan(
            session_id=session_id,
            plan=plan,
            lease=lease,
        )


def select_question(
    session_id,
    lease,
):

    with SessionLocal() as db:

        question = ResearchSessionRepository(
            db
        ).select_question_fenced(
            session_id=session_id,
            lease=lease,
        )

        if question is None:

            return None

        return (
            question.id,
            question.question,
            question.status,
        )


def complete_question(
    session_id,
    question_id,
    lease,
):

    with SessionLocal() as db:

        ResearchSessionRepository(
            db
        ).set_question_status_fenced(
            session_id=session_id,
            question_id=question_id,
            status="researched",
            lease=lease,
        )


def complete_research(
    session_id,
    lease,
):

    with SessionLocal() as db:

        ResearchSessionRepository(
            db
        ).complete_research_fenced(
            session_id=session_id,
            lease=lease,
        )


def get_questions(
    session_id,
):

    with SessionLocal() as db:

        rows = db.execute(
            text(
                """
                SELECT
                    id,
                    category,
                    question,
                    rationale,
                    status
                FROM dbo.research_questions
                WHERE research_session_id = :session_id
                ORDER BY id
                """
            ),
            {
                "session_id": session_id,
            },
        ).all()

        return [
            tuple(row)
            for row in rows
        ]


def session_status(
    session_id,
):

    return get_snapshot(
        session_id
    )[0]


def expect_rejection(
    operation,
    expected_exception,
    session_id,
):

    before_status = session_status(
        session_id
    )

    before_questions = get_questions(
        session_id
    )

    try:

        operation()

    except expected_exception:

        pass

    else:

        raise AssertionError(
            "Operation was unexpectedly accepted."
        )

    assert session_status(
        session_id
    ) == before_status

    assert get_questions(
        session_id
    ) == before_questions


def main():

    print()
    print("RESEARCH PLAN LIFECYCLE")
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
                "created",
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

        plan = make_plan()

        #
        # Enter planning through the
        # production lifecycle method.
        #

        prepare_execution(
            session_a,
            lease_a,
        )

        assert session_status(
            session_a
        ) == "planning"

        print(
            "TEST 1 - Planning entered: PASSED"
        )

        #
        # Persist the actual research plan.
        #

        save_plan(
            session_a,
            plan,
            lease_a,
        )

        assert session_status(
            session_a
        ) == "planned"

        questions = get_questions(
            session_a
        )

        assert len(questions) == 2

        assert all(
            question[4] == "pending"
            for question in questions
        )

        print(
            "TEST 2 - Research plan persisted: PASSED"
        )

        #
        # Repeated persistence of an
        # identical plan is idempotent.
        #

        before = get_questions(
            session_a
        )

        save_plan(
            session_a,
            plan,
            lease_a,
        )

        assert get_questions(
            session_a
        ) == before

        print(
            "TEST 3 - Identical plan idempotent: PASSED"
        )

        #
        # A conflicting plan must not
        # replace persisted questions.
        #

        conflicting_plan = make_plan()

        conflicting_plan.questions[0].question = (
            "A deliberately different question."
        )

        expect_rejection(
            lambda: save_plan(
                session_a,
                conflicting_plan,
                lease_a,
            ),
            ValueError,
            session_a,
        )

        print(
            "TEST 4 - Conflicting plan rejected: PASSED"
        )

        #
        # Resume must preserve the plan.
        #

        prepare_execution(
            session_a,
            lease_a,
            resume=True,
        )

        assert session_status(
            session_a
        ) == "planned"

        assert get_questions(
            session_a
        ) == before

        print(
            "TEST 5 - Planning recovery preserved: PASSED"
        )

        #
        # Question selection must persist
        # the active research question.
        #

        selected_a = select_question(
            session_a,
            lease_a,
        )

        assert selected_a is not None

        assert selected_a[2] == "researching"

        print(
            "TEST 6 - Question selection persisted: PASSED"
        )

        #
        # Repeated selection must return
        # the same active question.
        #

        selected_again = select_question(
            session_a,
            lease_a,
        )

        assert selected_again == selected_a

        print(
            "TEST 7 - Active question recovered: PASSED"
        )

        #
        # Complete the first question.
        #

        complete_question(
            session_a,
            selected_a[0],
            lease_a,
        )

        assert get_questions(
            session_a
        )[0][4] == "researched"

        print(
            "TEST 8 - First question completed: PASSED"
        )

        #
        # Research cannot finish while
        # another question is pending.
        #

        expect_rejection(
            lambda: complete_research(
                session_a,
                lease_a,
            ),
            ValueError,
            session_a,
        )

        print(
            "TEST 9 - Incomplete research rejected: PASSED"
        )

        #
        # Select and complete the next
        # research question.
        #

        selected_b = select_question(
            session_a,
            lease_a,
        )

        assert selected_b is not None

        assert selected_b[0] != selected_a[0]

        complete_question(
            session_a,
            selected_b[0],
            lease_a,
        )

        assert all(
            question[4] == "researched"
            for question in get_questions(
                session_a
            )
        )

        print(
            "TEST 10 - All questions completed: PASSED"
        )

        #
        # No pending or active questions
        # should remain.
        #

        assert select_question(
            session_a,
            lease_a,
        ) is None

        print(
            "TEST 11 - Question queue exhausted: PASSED"
        )

        #
        # Complete research through the
        # production repository.
        #

        complete_research(
            session_a,
            lease_a,
        )

        assert session_status(
            session_a
        ) == "researched"

        print(
            "TEST 12 - Research completed: PASSED"
        )

        #
        # Completion must be idempotent.
        #

        complete_research(
            session_a,
            lease_a,
        )

        assert session_status(
            session_a
        ) == "researched"

        print(
            "TEST 13 - Research completion idempotent: PASSED"
        )

        #
        # A newly created session cannot
        # persist a plan before planning.
        #

        expect_rejection(
            lambda: save_plan(
                session_b,
                plan,
                lease_b,
            ),
            ValueError,
            session_b,
        )

        print(
            "TEST 14 - Premature plan rejected: PASSED"
        )

        #
        # An expired execution lease
        # cannot persist a plan.
        #

        prepare_execution(
            session_b,
            lease_b,
        )

        expire_lease(
            session_b
        )

        expect_rejection(
            lambda: save_plan(
                session_b,
                plan,
                lease_b,
            ),
            ExecutionLeaseFenceRejected,
            session_b,
        )

        print(
            "TEST 15 - Expired plan lease rejected: PASSED"
        )

        #
        # Replacement ownership must
        # invalidate the previous worker.
        #

        replacement_b = acquire_lease(
            session_b
        )

        assert (
            replacement_b.version
            > lease_b.version
        )

        expect_rejection(
            lambda: save_plan(
                session_b,
                plan,
                lease_b,
            ),
            ExecutionLeaseFenceRejected,
            session_b,
        )

        print(
            "TEST 16 - Superseded plan lease rejected: PASSED"
        )

        #
        # The replacement worker can
        # persist the research plan.
        #

        save_plan(
            session_b,
            plan,
            replacement_b,
        )

        assert session_status(
            session_b
        ) == "planned"

        assert len(
            get_questions(
                session_b
            )
        ) == 2

        print(
            "TEST 17 - Replacement persists plan: PASSED"
        )

        #
        # Cross-session ownership must
        # be rejected.
        #

        expect_rejection(
            lambda: save_plan(
                session_c,
                plan,
                lease_a,
            ),
            ValueError,
            session_c,
        )

        print(
            "TEST 18 - Cross-session plan lease rejected: PASSED"
        )

        #
        # No other session may have been
        # modified by these operations.
        #

        assert session_status(
            session_c
        ) == "created"

        assert get_questions(
            session_c
        ) == []

        print(
            "TEST 19 - Session isolation preserved: PASSED"
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
