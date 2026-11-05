
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import event

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import (
    QuestionReview,
    ResearchQuestion,
)

from persistence.review_repository import (
    ReviewRepository,
)

from test_search_result_fencing import (
    create_session,
    delete_session,
    expire_lease,
)

from test_review_selection_fencing import (
    create_review_question,
)


def make_review():

    return SimpleNamespace(
        answer="Deterministic test answer.",
        overall_confidence=0.85,
        sufficient_evidence=True,
        reviewed_claims=[],
        contradictions=[],
        evidence_gaps=[],
    )


def create_reviewing_question(
    session_id,
):

    return create_review_question(
        session_id,
        "reviewing",
    )


def get_snapshot(
    question_id,
):

    with SessionLocal() as db:

        question = db.get(
            ResearchQuestion,
            question_id,
        )

        assert question is not None

        reviews = (
            db.query(
                QuestionReview
            )
            .filter(
                QuestionReview.research_question_id
                == question_id
            )
            .order_by(
                QuestionReview.id
            )
            .all()
        )

        return (
            question.status,
            tuple(
                (
                    review.id,
                    review.answer,
                    review.overall_confidence,
                    review.sufficient_evidence,
                )
                for review in reviews
            ),
        )


def save_review(
    session_id,
    question_id,
    lease,
    review=None,
    valid_finding_ids=None,
):

    if valid_finding_ids is None:

        valid_finding_ids = set()

    with SessionLocal() as db:

        return ReviewRepository(
            db
        ).save_review_fenced(
            session_id=session_id,
            question_id=question_id,
            review=review,
            valid_finding_ids=valid_finding_ids,
            lease=lease,
        )


def set_question_status(
    question_id,
    status,
):

    with SessionLocal() as db:

        question = db.get(
            ResearchQuestion,
            question_id,
        )

        assert question is not None

        question.status = status

        question.updated_at = datetime.now(
            timezone.utc
        )

        db.commit()


def expect_rejection(
    operation,
    question_ids,
    exception_type,
):

    before = {
        question_id: get_snapshot(question_id)
        for question_id in question_ids
    }

    try:

        operation()

    except exception_type:

        pass

    else:

        raise AssertionError(
            "Review persistence was unexpectedly accepted."
        )

    after = {
        question_id: get_snapshot(question_id)
        for question_id in question_ids
    }

    assert after == before, (
        "Rejected operation changed "
        "review persistence."
    )


def cleanup_reviews(
    session_id,
):

    with SessionLocal() as db:

        question_ids = [
            row[0]
            for row in (
                db.query(
                    ResearchQuestion.id
                )
                .filter(
                    ResearchQuestion.research_session_id
                    == session_id
                )
                .all()
            )
        ]

        if question_ids:

            db.query(
                QuestionReview
            ).filter(
                QuestionReview.research_question_id.in_(
                    question_ids
                )
            ).delete(
                synchronize_session=False
            )

        db.commit()


def main():

    print()
    print("REVIEW PERSISTENCE FENCING")
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

        question_a = create_reviewing_question(
            session_a
        )

        question_b = create_reviewing_question(
            session_b
        )

        question_c = create_reviewing_question(
            session_c
        )

        question_d = create_reviewing_question(
            session_d
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

        # A new review and its question status
        # must be persisted together.

        review_id_a = save_review(
            session_a,
            question_a,
            lease_a,
            make_review(),
        )

        snapshot_a = get_snapshot(
            question_a
        )

        assert snapshot_a[0] == "reviewed"
        assert len(snapshot_a[1]) == 1
        assert snapshot_a[1][0][0] == review_id_a

        print(
            "TEST 1 - Review and status persisted: PASSED"
        )

        # Repeating the operation must not
        # insert a second review.

        repeated_id = save_review(
            session_a,
            question_a,
            lease_a,
            make_review(),
        )

        assert repeated_id == review_id_a

        assert get_snapshot(
            question_a
        ) == snapshot_a

        print(
            "TEST 2 - Idempotent retry: PASSED"
        )

        # Simulate a previously persisted
        # review whose status was not updated.

        set_question_status(
            question_a,
            "reviewing",
        )

        recovered_id = save_review(
            session_a,
            question_a,
            lease_a,
            review=None,
        )

        assert recovered_id == review_id_a

        assert get_snapshot(
            question_a
        ) == snapshot_a

        print(
            "TEST 3 - Existing review recovery: PASSED"
        )

        # A question with no review cannot
        # be marked reviewed without supplying
        # a new review.

        expect_rejection(
            lambda: save_review(
                session_b,
                question_b,
                lease_b,
                review=None,
            ),
            [question_b],
            ValueError,
        )

        print(
            "TEST 4 - Missing review rejected: PASSED"
        )

        # A new review requires the question
        # to be in reviewing status.

        set_question_status(
            question_b,
            "researched",
        )

        expect_rejection(
            lambda: save_review(
                session_b,
                question_b,
                lease_b,
                make_review(),
            ),
            [question_b],
            ValueError,
        )

        print(
            "TEST 5 - Invalid question status rejected: PASSED"
        )

        set_question_status(
            question_b,
            "reviewing",
        )

        # Invalid owner.

        invalid_lease = replace(
            lease_b,
            owner=str(uuid4()),
        )

        expect_rejection(
            lambda: save_review(
                session_b,
                question_b,
                invalid_lease,
                make_review(),
            ),
            [question_b],
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 6 - Invalid owner rejected: PASSED"
        )

        # Expired execution lease.

        expire_lease(
            session_b
        )

        expect_rejection(
            lambda: save_review(
                session_b,
                question_b,
                lease_b,
                make_review(),
            ),
            [question_b],
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 7 - Expired lease rejected: PASSED"
        )

        # Acquire a replacement lease.

        with SessionLocal() as db:

            replacement_lease_b = (
                ExecutionLeaseRepository(db)
                .acquire(session_b)
            )

        expect_rejection(
            lambda: save_review(
                session_b,
                question_b,
                lease_b,
                make_review(),
            ),
            [question_b],
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 8 - Superseded lease rejected: PASSED"
        )

        # Cross-session lease.

        expect_rejection(
            lambda: save_review(
                session_b,
                question_b,
                lease_a,
                make_review(),
            ),
            [question_a, question_b],
            ValueError,
        )

        print(
            "TEST 9 - Cross-session lease rejected: PASSED"
        )

        # Cross-session question.

        expect_rejection(
            lambda: save_review(
                session_b,
                question_a,
                replacement_lease_b,
                make_review(),
            ),
            [question_a, question_b],
            ValueError,
        )

        print(
            "TEST 10 - Cross-session question rejected: PASSED"
        )

        # A supplied finding ID must exist
        # and belong to the selected question.

        expect_rejection(
            lambda: save_review(
                session_c,
                question_c,
                lease_c,
                make_review(),
                valid_finding_ids={
                    -999999
                },
            ),
            [question_c],
            ValueError,
        )

        print(
            "TEST 11 - Invalid evidence ownership rejected: PASSED"
        )

        # Simulate failure after SQLAlchemy
        # flushes the review insertion.

        before_c = get_snapshot(
            question_c
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

                    ReviewRepository(
                        db
                    ).save_review_fenced(
                        session_id=session_c,
                        question_id=question_c,
                        review=make_review(),
                        valid_finding_ids=set(),
                        lease=lease_c,
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
            question_c
        ) == before_c

        print(
            "TEST 12 - Atomic insertion rollback: PASSED"
        )

        # A valid retry must succeed after
        # the failed transaction.

        recovered_id_c = save_review(
            session_c,
            question_c,
            lease_c,
            make_review(),
        )

        assert recovered_id_c is not None

        assert get_snapshot(
            question_c
        )[0] == "reviewed"

        assert len(
            get_snapshot(question_c)[1]
        ) == 1

        print(
            "TEST 13 - Recovery after rollback: PASSED"
        )

        # Verify successful persistence
        # with a replacement lease.

        review_id_b = save_review(
            session_b,
            question_b,
            replacement_lease_b,
            make_review(),
        )

        assert review_id_b is not None

        assert get_snapshot(
            question_b
        )[0] == "reviewed"

        print(
            "TEST 14 - Replacement lease succeeds: PASSED"
        )

        # Session D must remain untouched.

        assert get_snapshot(
            question_d
        ) == (
            "reviewing",
            (),
        )

        print(
            "TEST 15 - Session isolation preserved: PASSED"
        )

        print()
        print("PASS")

    finally:

        for session_id in reversed(
            sessions
        ):

            cleanup_reviews(
                session_id
            )

            delete_session(
                session_id
            )


if __name__ == "__main__":

    main()
