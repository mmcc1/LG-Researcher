
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import event, func

from domain.review import (
    ResearchQuestionReview,
    ReviewedClaim,
)

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
)

from persistence.models import (
    Finding,
    Source,
    QuestionReview,
    ResearchQuestion,
    ReviewedClaimEntity,
    ReviewedClaimSupport,
    ReviewedClaimContradiction,
    ReviewContradiction,
    ReviewEvidenceGap,
)

from persistence.review_repository import (
    ReviewRepository,
)

from test_search_result_fencing import (
    create_session,
    delete_session,
)

from test_review_selection_fencing import (
    create_review_question,
)

from test_review_persistence_fencing import (
    cleanup_reviews,
    get_snapshot,
    save_review,
)

from sqlalchemy import text

from sqlalchemy.orm import Session


def create_source_and_findings(
    session_id,
    question_id,
    count=3,
):

    with SessionLocal() as db:

        url = (
            "https://example.com/review-test/"
            f"{uuid4()}"
        )

        source = Source(
            research_session_id=session_id,
            research_question_id=question_id,
            requested_url=url,
            final_url=url,
            title="Disposable review source",
            content_type="text/html",
            status_code=200,
            content_hash="0" * 64,
            raw_content="Test source content.",
            extracted_text="Test source content.",
            created_at=datetime.now(
                timezone.utc
            ),
        )

        db.add(source)
        db.flush()

        finding_ids = []

        for index in range(count):

            finding = Finding(
                source_id=source.id,
                research_question_id=question_id,
                claim=f"Test finding {index + 1}",
                evidence=f"Evidence {index + 1}",
                relevance="Relevant to the test.",
                confidence="high",
                created_at=datetime.now(
                    timezone.utc
                ),
            )

            db.add(finding)
            db.flush()

            finding_ids.append(
                finding.id
            )

        db.commit()

        return source.id, finding_ids


def make_review(
    finding_ids,
):

    return ResearchQuestionReview(
        answer="Evidence supports the test conclusion.",
        reviewed_claims=[
            ReviewedClaim(
                claim="First reviewed conclusion.",
                supporting_finding_ids=[
                    finding_ids[0],
                    finding_ids[1],
                ],
                contradicting_finding_ids=[
                    finding_ids[2],
                ],
                confidence="high",
            ),
            ReviewedClaim(
                claim="Second reviewed conclusion.",
                supporting_finding_ids=[
                    finding_ids[1],
                ],
                contradicting_finding_ids=[],
                confidence="medium",
            ),
        ],
        contradictions=[
            "The third finding challenges the first conclusion.",
        ],
        evidence_gaps=[
            "Additional independent evidence is needed.",
            "Long-term observations are unavailable.",
        ],
        overall_confidence="medium",
        sufficient_evidence=True,
    )


def get_provenance_snapshot(
    question_id,
):

    with SessionLocal() as db:

        reviews = (
            db.query(QuestionReview)
            .filter(
                QuestionReview.research_question_id
                == question_id
            )
            .all()
        )

        review_ids = [
            review.id
            for review in reviews
        ]

        if not review_ids:

            return {
                "reviews": 0,
                "claims": 0,
                "supports": 0,
                "contradicting_references": 0,
                "contradictions": 0,
                "gaps": 0,
            }

        claim_ids = [
            row[0]
            for row in (
                db.query(
                    ReviewedClaimEntity.id
                )
                .filter(
                    ReviewedClaimEntity.question_review_id.in_(
                        review_ids
                    )
                )
                .all()
            )
        ]

        def count(model, column, ids):

            if not ids:

                return 0

            return (
                db.query(
                    func.count()
                )
                .select_from(model)
                .filter(
                    column.in_(ids)
                )
                .scalar()
            )

        return {
            "reviews": len(reviews),
            "claims": count(
                ReviewedClaimEntity,
                ReviewedClaimEntity.question_review_id,
                review_ids,
            ),
            "supports": count(
                ReviewedClaimSupport,
                ReviewedClaimSupport.reviewed_claim_id,
                claim_ids,
            ),
            "contradicting_references": count(
                ReviewedClaimContradiction,
                ReviewedClaimContradiction.reviewed_claim_id,
                claim_ids,
            ),
            "contradictions": count(
                ReviewContradiction,
                ReviewContradiction.question_review_id,
                review_ids,
            ),
            "gaps": count(
                ReviewEvidenceGap,
                ReviewEvidenceGap.question_review_id,
                review_ids,
            ),
        }


def delete_provenance(
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

        review_ids = [
            row[0]
            for row in (
                db.query(
                    QuestionReview.id
                )
                .filter(
                    QuestionReview.research_question_id.in_(
                        question_ids
                    )
                )
                .all()
            )
        ] if question_ids else []

        claim_ids = [
            row[0]
            for row in (
                db.query(
                    ReviewedClaimEntity.id
                )
                .filter(
                    ReviewedClaimEntity.question_review_id.in_(
                        review_ids
                    )
                )
                .all()
            )
        ] if review_ids else []

        if claim_ids:

            db.query(
                ReviewedClaimSupport
            ).filter(
                ReviewedClaimSupport.reviewed_claim_id.in_(
                    claim_ids
                )
            ).delete(synchronize_session=False)

            db.query(
                ReviewedClaimContradiction
            ).filter(
                ReviewedClaimContradiction.reviewed_claim_id.in_(
                    claim_ids
                )
            ).delete(synchronize_session=False)

        if review_ids:

            for model in (
                ReviewedClaimEntity,
                ReviewContradiction,
                ReviewEvidenceGap,
            ):

                db.query(model).filter(
                    model.question_review_id.in_(
                        review_ids
                    )
                ).delete(
                    synchronize_session=False
                )

            db.query(
                QuestionReview
            ).filter(
                QuestionReview.id.in_(
                    review_ids
                )
            ).delete(
                synchronize_session=False
            )

        if question_ids:

            db.query(Finding).filter(
                Finding.research_question_id.in_(
                    question_ids
                )
            ).delete(
                synchronize_session=False
            )

            db.query(Source).filter(
                Source.research_question_id.in_(
                    question_ids
                )
            ).delete(
                synchronize_session=False
            )

        db.commit()



def expect_foreign_finding_rejected(
    session_id,
    question_id,
    lease,
    local_finding_ids,
    foreign_finding_id,
):

    review = make_review(
        [
            foreign_finding_id,
            local_finding_ids[1],
            local_finding_ids[2],
        ]
    )

    before = get_provenance_snapshot(
        question_id
    )

    before_status = get_snapshot(
        question_id
    )[0]

    try:

        save_review(
            session_id,
            question_id,
            lease,
            review,
            set(local_finding_ids) | {
                foreign_finding_id
            },
        )

    except ValueError:

        pass

    else:

        raise AssertionError(
            "Foreign finding was accepted "
            "despite belonging to another question."
        )

    assert get_provenance_snapshot(
        question_id
    ) == before

    assert get_snapshot(
        question_id
    )[0] == before_status




def expect_status_update_rollback(
    session_id,
    question_id,
    lease,
    review,
    finding_ids,
):

    before = get_provenance_snapshot(
        question_id
    )

    before_status = get_snapshot(
        question_id
    )[0]

    with SessionLocal() as db:

        original_flush = db.flush

        flush_count = 0

        def failing_flush(
            objects=None,
        ):

            nonlocal flush_count

            flush_count += 1

            #
            # The review header and reviewed
            # claim entities are flushed first.
            #
            # The final flush persists remaining
            # provenance records and question
            # status together.
            #

            if flush_count == 5:

                raise RuntimeError(
                    "Simulated final persistence failure."
                )

            return original_flush(
                objects=objects
            )

        db.flush = failing_flush

        try:

            try:

                ReviewRepository(
                    db
                ).save_review_fenced(
                    session_id=session_id,
                    question_id=question_id,
                    review=review,
                    valid_finding_ids=set(
                        finding_ids
                    ),
                    lease=lease,
                )

            except RuntimeError as exc:

                assert str(exc) == (
                    "Simulated final persistence failure."
                )

            else:

                raise AssertionError(
                    "Expected final persistence failure."
                )

        finally:

            db.flush = original_flush

    assert get_provenance_snapshot(
        question_id
    ) == before

    assert get_snapshot(
        question_id
    )[0] == before_status


def main():

    print()
    print("REVIEW PROVENANCE FENCING")
    print("=========================")

    sessions = []

    try:

        session_a = create_session()
        sessions.append(session_a)

        session_b = create_session()
        sessions.append(session_b)

        question_a = create_review_question(
            session_a,
            "reviewing",
        )

        question_b = create_review_question(
            session_b,
            "reviewing",
        )

        _, finding_ids_a = (
            create_source_and_findings(
                session_a,
                question_a,
            )
        )

        _, finding_ids_b = (
            create_source_and_findings(
                session_b,
                question_b,
            )
        )

        with SessionLocal() as db:

            lease_a = ExecutionLeaseRepository(
                db
            ).acquire(session_a)

            lease_b = ExecutionLeaseRepository(
                db
            ).acquire(session_b)

        review = make_review(
            finding_ids_a
        )

        review_id = save_review(
            session_a,
            question_a,
            lease_a,
            review,
            set(finding_ids_a),
        )

        assert review_id is not None

        assert get_snapshot(
            question_a
        )[0] == "reviewed"

        expected = {
            "reviews": 1,
            "claims": 2,
            "supports": 3,
            "contradicting_references": 1,
            "contradictions": 1,
            "gaps": 2,
        }

        assert get_provenance_snapshot(
            question_a
        ) == expected

        print(
            "TEST 1 - Complete provenance persisted: PASSED"
        )

        repeated_id = save_review(
            session_a,
            question_a,
            lease_a,
            review,
            set(finding_ids_a),
        )

        assert repeated_id == review_id

        assert get_provenance_snapshot(
            question_a
        ) == expected

        print(
            "TEST 2 - Provenance retry idempotent: PASSED"
        )

        # A foreign finding reference must
        # be rejected before insertion.

        invalid_review = make_review(
            [
                finding_ids_b[0],
                finding_ids_a[1],
                finding_ids_a[2],
            ]
        )

        before_b = get_provenance_snapshot(
            question_b
        )

        try:

            save_review(
                session_b,
                question_b,
                lease_b,
                invalid_review,
                set(finding_ids_a),
            )

        except ValueError:

            pass

        else:

            raise AssertionError(
                "Cross-question evidence was accepted."
            )

        assert get_provenance_snapshot(
            question_b
        ) == before_b

        print(
            "TEST 3 - Foreign evidence rejected: PASSED"
        )

        # Inject a failure after review insertion
        # has begun, before transaction commit.

        valid_review_b = make_review(
            finding_ids_b
        )

        before_b = get_provenance_snapshot(
            question_b
        )

        with SessionLocal() as db:

            flush_count = 0

            def fail_during_flush(
                session,
                flush_context,
            ):

                nonlocal flush_count

                flush_count += 1

                if flush_count == 2:

                    raise RuntimeError(
                        "Simulated provenance failure."
                    )

            event.listen(
                db,
                "after_flush",
                fail_during_flush,
            )

            try:

                try:

                    ReviewRepository(
                        db
                    ).save_review_fenced(
                        session_id=session_b,
                        question_id=question_b,
                        review=valid_review_b,
                        valid_finding_ids=set(
                            finding_ids_b
                        ),
                        lease=lease_b,
                    )

                except RuntimeError as exc:

                    assert str(exc) == (
                        "Simulated provenance failure."
                    )

                else:

                    raise AssertionError(
                        "Expected provenance failure."
                    )

            finally:

                event.remove(
                    db,
                    "after_flush",
                    fail_during_flush,
                )

        assert get_provenance_snapshot(
            question_b
        ) == before_b

        assert get_snapshot(
            question_b
        )[0] == "reviewing"

        print(
            "TEST 4 - Partial provenance rollback: PASSED"
        )

        recovered_id = save_review(
            session_b,
            question_b,
            lease_b,
            valid_review_b,
            set(finding_ids_b),
        )

        assert recovered_id is not None

        assert get_provenance_snapshot(
            question_b
        ) == expected

        assert get_snapshot(
            question_b
        )[0] == "reviewed"

        print(
            "TEST 5 - Recovery after rollback: PASSED"
        )

        
        session_c = create_session()
        sessions.append(session_c)

        question_c = create_review_question(
            session_c,
            "reviewing",
        )

        _, finding_ids_c = (
            create_source_and_findings(
                session_c,
                question_c,
            )
        )

        with SessionLocal() as db:

            lease_c = ExecutionLeaseRepository(
                db
            ).acquire(session_c)

        # Foreign finding included in the
        # caller's allowed finding set.

        expect_foreign_finding_rejected(
            session_id=session_c,
            question_id=question_c,
            lease=lease_c,
            local_finding_ids=finding_ids_c,
            foreign_finding_id=finding_ids_a[0],
        )

        print(
            "TEST 6 - Database finding ownership enforced: PASSED"
        )

        # Failure after all provenance insertion
        # flushes, during the final persistence step.

        expect_status_update_rollback(
            session_id=session_c,
            question_id=question_c,
            lease=lease_c,
            review=make_review(
                finding_ids_c
            ),
            finding_ids=finding_ids_c,
        )

        print(
            "TEST 7 - Final persistence rollback: PASSED"
        )

        # A normal retry must succeed.

        review_id_c = save_review(
            session_c,
            question_c,
            lease_c,
            make_review(
                finding_ids_c
            ),
            set(finding_ids_c),
        )

        assert review_id_c is not None

        assert get_provenance_snapshot(
            question_c
        ) == expected

        assert get_snapshot(
            question_c
        )[0] == "reviewed"

        print(
            "TEST 8 - Recovery after final rollback: PASSED"
        )


        print()
        print("PASS")

    finally:

        for session_id in reversed(
            sessions
        ):

            delete_provenance(
                session_id
            )

            delete_session(
                session_id
            )


if __name__ == "__main__":

    main()
