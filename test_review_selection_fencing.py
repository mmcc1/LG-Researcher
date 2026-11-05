
from datetime import datetime, timezone
from dataclasses import replace
from uuid import uuid4

from sqlalchemy import event, text

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import (
    ResearchQuestion,
    ResearchSession,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from test_search_result_fencing import (
    create_session,
    delete_session,
    expire_lease,
)


def create_review_question(
    session_id: str,
    status: str = "researched",
) -> int:

    with SessionLocal() as db:

        question = ResearchQuestion(
            research_session_id=session_id,
            category="Testing",
            question=f"Review question {uuid4()}",
            rationale="Disposable review test.",
            status=status,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        db.add(question)
        db.commit()

        return question.id


def set_session_status(
    session_id: str,
    status: str,
) -> None:

    with SessionLocal() as db:

        session = db.get(
            ResearchSession,
            session_id,
        )

        assert session is not None

        session.status = status

        db.commit()


def get_snapshot(
    session_id: str,
):

    with SessionLocal() as db:

        session = db.get(
            ResearchSession,
            session_id,
        )

        assert session is not None

        questions = (
            db.query(ResearchQuestion)
            .filter(
                ResearchQuestion.research_session_id
                == session_id
            )
            .order_by(ResearchQuestion.id)
            .all()
        )

        return (
            session.status,
            tuple(
                (
                    question.id,
                    question.status,
                )
                for question in questions
            ),
        )


def select_review(
    session_id,
    lease,
):

    with SessionLocal() as db:

        question = (
            ResearchSessionRepository(db)
            .select_review_question_fenced(
                session_id=session_id,
                lease=lease,
            )
        )

        if question is None:

            return None

        return (
            question.id,
            question.question,
            question.status,
        )


def expect_rejection(
    operation,
    session_ids,
    exception_type,
):

    before = {
        session_id: get_snapshot(session_id)
        for session_id in session_ids
    }

    try:

        operation()

    except exception_type:

        pass

    else:

        raise AssertionError(
            "Review selection was unexpectedly accepted."
        )

    after = {
        session_id: get_snapshot(session_id)
        for session_id in session_ids
    }

    assert after == before, (
        "Rejected review selection changed "
        "database persistence."
    )


def main():

    print()
    print("REVIEW SELECTION FENCING")
    print("========================")

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

        question_a1 = create_review_question(
            session_a,
            "researched",
        )

        question_a2 = create_review_question(
            session_a,
            "researched",
        )

        question_b1 = create_review_question(
            session_b,
            "reviewing",
        )

        question_b2 = create_review_question(
            session_b,
            "researched",
        )

        question_c = create_review_question(
            session_c,
            "pending",
        )

        question_d = create_review_question(
            session_d,
            "researched",
        )

        for session_id in sessions:

            set_session_status(
                session_id,
                "researching",
            )

        with SessionLocal() as db:

            lease_a = ExecutionLeaseRepository(
                db
            ).acquire(session_a)

            lease_b = ExecutionLeaseRepository(
                db
            ).acquire(session_b)

            lease_c = ExecutionLeaseRepository(
                db
            ).acquire(session_c)

            lease_d = ExecutionLeaseRepository(
                db
            ).acquire(session_d)

        # Select the first researched question.

        result = select_review(
            session_a,
            lease_a,
        )

        assert result is not None
        assert result[0] == question_a1
        assert result[2] == "reviewing"

        snapshot = get_snapshot(session_a)

        assert snapshot[0] == "reviewing"

        assert snapshot[1] == (
            (question_a1, "reviewing"),
            (question_a2, "researched"),
        )

        print(
            "TEST 1 - First eligible question selected: PASSED"
        )

        # Repeated selection recovers the same question.

        result = select_review(
            session_a,
            lease_a,
        )

        assert result[0] == question_a1

        assert get_snapshot(session_a) == snapshot

        print(
            "TEST 2 - Active review recovered: PASSED"
        )

        # An existing reviewing question takes
        # priority over another researched question.

        result = select_review(
            session_b,
            lease_b,
        )

        assert result[0] == question_b1

        assert get_snapshot(session_b) == (
            "reviewing",
            (
                (question_b1, "reviewing"),
                (question_b2, "researched"),
            ),
        )

        print(
            "TEST 3 - Active review takes priority: PASSED"
        )

        # No eligible question must leave the
        # session status unchanged.

        before_c = get_snapshot(
            session_c
        )

        result = select_review(
            session_c,
            lease_c,
        )

        assert result is None

        assert get_snapshot(
            session_c
        ) == before_c

        print(
            "TEST 4 - No eligible question: PASSED"
        )

        # Invalid lease owner.

        invalid_lease = replace(
            lease_d,
            owner=str(uuid4()),
        )

        expect_rejection(
            lambda: select_review(
                session_d,
                invalid_lease,
            ),
            [session_d],
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 5 - Invalid owner rejected: PASSED"
        )

        # Expired lease.

        expire_lease(
            session_d
        )

        expect_rejection(
            lambda: select_review(
                session_d,
                lease_d,
            ),
            [session_d],
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 6 - Expired lease rejected: PASSED"
        )

        # Replace the expired lease.

        with SessionLocal() as db:

            replacement_lease_d = (
                ExecutionLeaseRepository(db)
                .acquire(session_d)
            )

        expect_rejection(
            lambda: select_review(
                session_d,
                lease_d,
            ),
            [session_d],
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 7 - Superseded lease rejected: PASSED"
        )

        # Cross-session lease.

        expect_rejection(
            lambda: select_review(
                session_d,
                lease_a,
            ),
            [session_a, session_d],
            ValueError,
        )

        print(
            "TEST 8 - Cross-session lease rejected: PASSED"
        )

        # Force a flush failure and verify that
        # neither status update survives.

        before_d = get_snapshot(
            session_d
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
                    ).select_review_question_fenced(
                        session_id=session_d,
                        lease=replacement_lease_d,
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

        assert get_snapshot(
            session_d
        ) == before_d

        print(
            "TEST 9 - Atomic rollback: PASSED"
        )

        # Retry after the rolled-back transaction.

        result = select_review(
            session_d,
            replacement_lease_d,
        )

        assert result is not None
        assert result[0] == question_d
        assert result[2] == "reviewing"

        assert get_snapshot(
            session_d
        )[0] == "reviewing"

        print(
            "TEST 10 - Recovery after rollback: PASSED"
        )

        # Confirm that other sessions were
        # not changed by the failed operation.

        assert get_snapshot(
            session_a
        ) == snapshot

        assert get_snapshot(
            session_c
        ) == before_c

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
