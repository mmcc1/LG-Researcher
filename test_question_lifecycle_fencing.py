
from dataclasses import replace
from uuid import uuid4

from sqlalchemy import event

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import ResearchQuestion

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from test_search_result_fencing import (
    create_session,
    create_question,
    delete_session,
    expire_lease,
)


def set_question_status(
    question_id: int,
    status: str,
) -> None:

    with SessionLocal() as db:

        question = db.get(
            ResearchQuestion,
            question_id,
        )

        assert question is not None

        question.status = status

        db.commit()


def get_question_status(
    question_id: int,
) -> str:

    with SessionLocal() as db:

        question = db.get(
            ResearchQuestion,
            question_id,
        )

        assert question is not None

        return question.status


def select_question(
    session_id,
    lease,
):

    with SessionLocal() as db:

        question = (
            ResearchSessionRepository(db)
            .select_question_fenced(
                session_id=session_id,
                lease=lease,
            )
        )

        if question is None:

            return None

        return question.id


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


def expect_rejection(
    operation,
    question_ids,
    exception_type,
):

    before = {
        question_id: get_question_status(
            question_id
        )
        for question_id in question_ids
    }

    try:

        operation()

    except exception_type:

        pass

    else:

        raise AssertionError(
            "Question operation was "
            "unexpectedly accepted."
        )

    after = {
        question_id: get_question_status(
            question_id
        )
        for question_id in question_ids
    }

    assert after == before, (
        "Rejected operation changed "
        "question status."
    )


def main():

    print()
    print("QUESTION LIFECYCLE FENCING")
    print("==========================")

    session_a = create_session()
    session_b = create_session()

    try:

        question_a = create_question(
            session_a
        )

        question_b = create_question(
            session_b
        )

        set_question_status(
            question_a,
            "pending",
        )

        set_question_status(
            question_b,
            "pending",
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

        # Select a pending question.

        selected_id = select_question(
            session_a,
            lease_a,
        )

        assert selected_id == question_a

        assert get_question_status(
            question_a
        ) == "researching"

        print(
            "TEST 1 - Pending question selected: PASSED"
        )

        # Repeated selection resumes
        # the active question.

        selected_id = select_question(
            session_a,
            lease_a,
        )

        assert selected_id == question_a

        assert get_question_status(
            question_a
        ) == "researching"

        print(
            "TEST 2 - Active question resumed: PASSED"
        )

        # Complete the selected question.

        complete_question(
            session_a,
            question_a,
            lease_a,
        )

        assert get_question_status(
            question_a
        ) == "researched"

        print(
            "TEST 3 - Question completed: PASSED"
        )

        # Repeating completion must
        # preserve the completed state.

        complete_question(
            session_a,
            question_a,
            lease_a,
        )

        assert get_question_status(
            question_a
        ) == "researched"

        print(
            "TEST 4 - Completion retry idempotent: PASSED"
        )

        # No remaining pending or active
        # questions in this session.

        assert select_question(
            session_a,
            lease_a,
        ) is None

        print(
            "TEST 5 - No remaining question: PASSED"
        )

        # A pending question cannot
        # be completed directly.

        expect_rejection(
            lambda: complete_question(
                session_b,
                question_b,
                lease_b,
            ),
            [question_b],
            ValueError,
        )

        print(
            "TEST 6 - Invalid transition rejected: PASSED"
        )

        # Incorrect execution owner.

        invalid_lease = replace(
            lease_b,
            owner=str(uuid4()),
        )

        expect_rejection(
            lambda: select_question(
                session_b,
                invalid_lease,
            ),
            [question_b],
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 7 - Incorrect owner rejected: PASSED"
        )

        # Expired execution lease.

        expire_lease(
            session_b
        )

        expect_rejection(
            lambda: select_question(
                session_b,
                lease_b,
            ),
            [question_b],
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 8 - Expired lease rejected: PASSED"
        )

        # Acquire a replacement lease.

        with SessionLocal() as db:

            replacement_lease_b = (
                ExecutionLeaseRepository(db)
                .acquire(
                    session_b
                )
            )

        expect_rejection(
            lambda: select_question(
                session_b,
                lease_b,
            ),
            [question_b],
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 9 - Superseded lease rejected: PASSED"
        )

        # Cross-session execution lease.

        expect_rejection(
            lambda: select_question(
                session_b,
                lease_a,
            ),
            [question_b],
            ValueError,
        )

        print(
            "TEST 10 - Cross-session lease rejected: PASSED"
        )

        # A valid lease cannot complete
        # another session's question.

        expect_rejection(
            lambda: complete_question(
                session_b,
                question_a,
                replacement_lease_b,
            ),
            [
                question_a,
                question_b,
            ],
            ValueError,
        )

        print(
            "TEST 11 - Cross-session question rejected: PASSED"
        )

        # Simulate failure during
        # selection's database flush.

        before = get_question_status(
            question_b
        )

        with SessionLocal() as db:

            def fail_after_flush(
                session,
                flush_context,
            ):

                raise RuntimeError(
                    "Simulated transaction failure."
                )

            event.listen(
                db,
                "after_flush",
                fail_after_flush,
            )

            try:

                try:

                    ResearchSessionRepository(
                        db
                    ).select_question_fenced(
                        session_id=session_b,
                        lease=replacement_lease_b,
                    )

                except RuntimeError as exc:

                    assert str(exc) == (
                        "Simulated transaction failure."
                    )

                else:

                    raise AssertionError(
                        "Expected transaction failure."
                    )

            finally:

                event.remove(
                    db,
                    "after_flush",
                    fail_after_flush,
                )

        assert get_question_status(
            question_b
        ) == before

        print(
            "TEST 12 - Selection rollback: PASSED"
        )

        # Selection must recover after
        # the failed transaction.

        assert select_question(
            session_b,
            replacement_lease_b,
        ) == question_b

        assert get_question_status(
            question_b
        ) == "researching"

        print(
            "TEST 13 - Selection recovery: PASSED"
        )

        # Simulate failure during
        # completion's database flush.

        with SessionLocal() as db:

            def fail_completion_flush(
                session,
                flush_context,
            ):

                raise RuntimeError(
                    "Simulated completion failure."
                )

            event.listen(
                db,
                "after_flush",
                fail_completion_flush,
            )

            try:

                try:

                    ResearchSessionRepository(
                        db
                    ).set_question_status_fenced(
                        session_id=session_b,
                        question_id=question_b,
                        status="researched",
                        lease=replacement_lease_b,
                    )

                except RuntimeError as exc:

                    assert str(exc) == (
                        "Simulated completion failure."
                    )

                else:

                    raise AssertionError(
                        "Expected completion failure."
                    )

            finally:

                event.remove(
                    db,
                    "after_flush",
                    fail_completion_flush,
                )

        assert get_question_status(
            question_b
        ) == "researching"

        print(
            "TEST 14 - Completion rollback: PASSED"
        )

        # Completion must recover.

        complete_question(
            session_b,
            question_b,
            replacement_lease_b,
        )

        assert get_question_status(
            question_b
        ) == "researched"

        print(
            "TEST 15 - Completion recovery: PASSED"
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
