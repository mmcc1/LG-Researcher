
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
    create_review_question,
)


def prepare_execution(
    session_id,
    lease,
    resume,
):

    with SessionLocal() as db:

        return ResearchSessionRepository(
            db
        ).prepare_execution_fenced(
            session_id=session_id,
            lease=lease,
            resume=resume,
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


def set_question_status(
    session_id,
    question_id,
    status,
    lease,
):

    with SessionLocal() as db:

        ResearchSessionRepository(
            db
        ).set_question_status_fenced(
            session_id=session_id,
            question_id=question_id,
            status=status,
            lease=lease,
        )


def create_question(
    session_id,
    status="pending",
):

    return create_review_question(
        session_id,
        status=status,
    )


def question_status(
    question_id,
):

    with SessionLocal() as db:

        return db.execute(
            text(
                """
                SELECT status
                FROM dbo.research_questions
                WHERE id = :question_id
                """
            ),
            {
                "question_id": question_id,
            },
        ).scalar_one()


def expect_rejection(
    operation,
    expected_exception,
    protected_sessions,
):

    before = {
        session_id: get_snapshot(
            session_id
        )
        for session_id in protected_sessions
    }

    try:

        operation()

    except expected_exception:

        pass

    else:

        raise AssertionError(
            "Lifecycle operation was "
            "unexpectedly accepted."
        )

    after = {
        session_id: get_snapshot(
            session_id
        )
        for session_id in protected_sessions
    }

    assert after == before, (
        "Rejected lifecycle operation "
        "modified persisted session state."
    )


def main():

    print()
    print("WORKFLOW LIFECYCLE FENCING")
    print("==========================")

    sessions = []

    try:

        session_a = create_session()
        sessions.append(session_a)

        session_b = create_session()
        sessions.append(session_b)

        session_c = create_session()
        sessions.append(session_c)

        session_d = create_session()
        sessions.append(session_d)

        session_e = create_session()
        sessions.append(session_e)

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

        lease_d = acquire_lease(
            session_d
        )

        lease_e = acquire_lease(
            session_e
        )

        #
        # Enter planning.
        #

        topic, scope = prepare_execution(
            session_a,
            lease_a,
            resume=False,
        )

        assert topic is not None

        assert get_snapshot(
            session_a
        )[0] == "planning"

        print(
            "TEST 1 - Planning transition persisted: PASSED"
        )

        #
        # Repeated workflow entry.
        #

        before = get_snapshot(
            session_a
        )

        prepare_execution(
            session_a,
            lease_a,
            resume=False,
        )

        assert get_snapshot(
            session_a
        ) == before

        print(
            "TEST 2 - Planning entry idempotent: PASSED"
        )

        #
        # Resume must preserve lifecycle.
        #

        set_session_status(
            session_b,
            "researched",
        )

        prepare_execution(
            session_b,
            lease_b,
            resume=True,
        )

        assert get_snapshot(
            session_b
        )[0] == "researched"

        print(
            "TEST 3 - Resume preserves lifecycle: PASSED"
        )

        #
        # New execution cannot reset a
        # previously researched session.
        #

        expect_rejection(
            lambda: prepare_execution(
                session_b,
                lease_b,
                resume=False,
            ),
            ValueError,
            [session_b],
        )

        print(
            "TEST 4 - Lifecycle regression rejected: PASSED"
        )

        #
        # Completed sessions cannot be
        # prepared for execution.
        #

        set_session_status(
            session_b,
            "completed",
        )

        expect_rejection(
            lambda: prepare_execution(
                session_b,
                lease_b,
                resume=True,
            ),
            ValueError,
            [session_b],
        )

        print(
            "TEST 5 - Completed session rejected: PASSED"
        )

        #
        # Invalid execution ownership.
        #

        invalid_lease = replace(
            lease_c,
            owner=str(uuid4()),
        )

        expect_rejection(
            lambda: prepare_execution(
                session_c,
                invalid_lease,
                resume=False,
            ),
            ExecutionLeaseFenceRejected,
            [session_c],
        )

        print(
            "TEST 6 - Incorrect owner rejected: PASSED"
        )

        #
        # Expired lease.
        #

        expire_lease(
            session_c
        )

        expect_rejection(
            lambda: prepare_execution(
                session_c,
                lease_c,
                resume=False,
            ),
            ExecutionLeaseFenceRejected,
            [session_c],
        )

        print(
            "TEST 7 - Expired entry lease rejected: PASSED"
        )

        #
        # Replacement ownership.
        #

        replacement_c = acquire_lease(
            session_c
        )

        assert (
            replacement_c.version
            > lease_c.version
        )

        expect_rejection(
            lambda: prepare_execution(
                session_c,
                lease_c,
                resume=False,
            ),
            ExecutionLeaseFenceRejected,
            [session_c],
        )

        print(
            "TEST 8 - Superseded entry rejected: PASSED"
        )

        prepare_execution(
            session_c,
            replacement_c,
            resume=False,
        )

        assert get_snapshot(
            session_c
        )[0] == "planning"

        print(
            "TEST 9 - Replacement entry succeeds: PASSED"
        )

        #
        # Empty research plan must not
        # be completed.
        #

        expect_rejection(
            lambda: complete_research(
                session_a,
                lease_a,
            ),
            ValueError,
            [session_a],
        )

        print(
            "TEST 10 - Empty research plan rejected: PASSED"
        )

        #
        # Create two research questions.
        #

        question_a1 = create_question(
            session_a,
            status="researching",
        )

        question_a2 = create_question(
            session_a,
            status="pending",
        )

        expect_rejection(
            lambda: complete_research(
                session_a,
                lease_a,
            ),
            ValueError,
            [session_a],
        )

        print(
            "TEST 11 - Unfinished research rejected: PASSED"
        )

        #
        # Complete the first question.
        #

        set_question_status(
            session_a,
            question_a1,
            "researched",
            lease_a,
        )

        assert question_status(
            question_a1
        ) == "researched"

        print(
            "TEST 12 - Question completion persisted: PASSED"
        )

        #
        # Pending questions must first
        # enter researching.
        #

        expect_rejection(
            lambda: set_question_status(
                session_a,
                question_a2,
                "researched",
                lease_a,
            ),
            ValueError,
            [session_a],
        )

        print(
            "TEST 13 - Invalid question transition rejected: PASSED"
        )

        set_question_status(
            session_a,
            question_a2,
            "researching",
            lease_a,
        )

        set_question_status(
            session_a,
            question_a2,
            "researched",
            lease_a,
        )

        assert question_status(
            question_a2
        ) == "researched"

        print(
            "TEST 14 - All questions researched: PASSED"
        )

        #
        # The research plan has been persisted.
        # The session must be in the planned
        # state before research can complete.
        #

        set_session_status(
            session_a,
            "planned",
        )

        #
        # Complete the overall research
        # phase.
        #

        complete_research(
            session_a,
            lease_a,
        )

        assert get_snapshot(
            session_a
        )[0] == "researched"

        print(
            "TEST 15 - Research completion persisted: PASSED"
        )

        #
        # Idempotent research completion.
        #

        before = get_snapshot(
            session_a
        )

        complete_research(
            session_a,
            lease_a,
        )

        assert get_snapshot(
            session_a
        ) == before

        print(
            "TEST 16 - Research completion idempotent: PASSED"
        )

        #
        # Research cannot complete from
        # an invalid lifecycle state.
        #

        question_d = create_question(
            session_d,
            status="researched",
        )

        expect_rejection(
            lambda: complete_research(
                session_d,
                lease_d,
            ),
            ValueError,
            [session_d],
        )

        print(
            "TEST 17 - Invalid completion lifecycle rejected: PASSED"
        )

        #
        # Research completion must
        # reject expired ownership.
        #

        set_session_status(
            session_d,
            "planning",
        )

        expire_lease(
            session_d
        )

        expect_rejection(
            lambda: complete_research(
                session_d,
                lease_d,
            ),
            ExecutionLeaseFenceRejected,
            [session_d],
        )

        print(
            "TEST 18 - Expired completion lease rejected: PASSED"
        )

        
        #
        # Acquire replacement execution ownership.
        #

        replacement_d = acquire_lease(
            session_d
        )

        assert (
            replacement_d.version
            > lease_d.version
        )

        #
        # The research session is now ready
        # for completion.
        #

        set_session_status(
            session_d,
            "planned",
        )

        #
        # The superseded worker must not
        # complete research.
        #

        expect_rejection(
            lambda: complete_research(
                session_d,
                lease_d,
            ),
            ExecutionLeaseFenceRejected,
            [session_d],
        )

        print(
            "TEST 19 - Superseded completion rejected: PASSED"
        )

        #
        # The replacement worker must be
        # able to complete the same research.
        #

        complete_research(
            session_d,
            replacement_d,
        )

        assert get_snapshot(
            session_d
        )[0] == "researched"

        print(
            "TEST 20 - Replacement completes research: PASSED"
        )


        #
        # Cross-session lease.
        #

        expect_rejection(
            lambda: complete_research(
                session_e,
                lease_a,
            ),
            ValueError,
            [session_a, session_e],
        )

        print(
            "TEST 21 - Cross-session lease rejected: PASSED"
        )

        #
        # Session isolation.
        #

        assert get_snapshot(
            session_a
        )[0] == "researched"

        assert get_snapshot(
            session_b
        )[0] == "completed"

        assert get_snapshot(
            session_c
        )[0] == "planning"

        assert get_snapshot(
            session_d
        )[0] == "researched"

        assert get_snapshot(
            session_e
        )[0] == "created"

        print(
            "TEST 22 - Session isolation preserved: PASSED"
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
