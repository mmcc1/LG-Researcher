
from datetime import datetime, timezone

from sqlalchemy import (
    event,
    text,
)

from domain.report import (
    ResearchReport,
    ReportSection,
)

from persistence.database import (
    SessionLocal,
)

from persistence.models import (
    QuestionReview,
    ReviewedClaimEntity,
)

from persistence.report_repository import (
    ReportRepository,
)

from test_search_result_fencing import (
    create_session,
    delete_session,
)

from test_review_completion_fencing import (
    acquire_lease,
)

from test_review_selection_fencing import (
    create_review_question,
    set_session_status,
)

from test_report_persistence_fencing import (
    delete_report,
)


def create_reviewed_claims(
    session_id,
    count=3,
):

    question_id = create_review_question(
        session_id,
        "reviewed",
    )

    with SessionLocal() as db:

        review = QuestionReview(
            research_question_id=question_id,
            answer="Deterministic review answer.",
            overall_confidence="high",
            sufficient_evidence=True,
            created_at=datetime.now(
                timezone.utc
            ),
        )

        db.add(review)
        db.flush()

        claim_ids = []

        for index in range(count):

            claim = ReviewedClaimEntity(
                question_review_id=review.id,
                claim=f"Reviewed claim {index + 1}",
                confidence="high",
            )

            db.add(claim)
            db.flush()

            claim_ids.append(
                claim.id
            )

        db.commit()

        return question_id, claim_ids


def make_report(
    claim_ids,
):

    return ResearchReport(
        title="Provenance Verification Report",
        executive_summary=(
            "A deterministic summary."
        ),
        sections=[
            ReportSection(
                heading="First Section",
                content="Evidence-based content.",
                reviewed_claim_ids=[
                    claim_ids[0],
                    claim_ids[1],
                    claim_ids[0],
                ],
            ),
            ReportSection(
                heading="Second Section",
                content="Additional reviewed evidence.",
                reviewed_claim_ids=[
                    claim_ids[1],
                    claim_ids[2],
                ],
            ),
        ],
        conclusions=(
            "Conclusions based on reviewed claims."
        ),
        limitations=[
            "Limited evidence coverage.",
            "Further verification required.",
        ],
    )


def persist_report(
    session_id,
    report,
    lease,
):

    with SessionLocal() as db:

        return ReportRepository(
            db
        ).save_report_fenced(
            session_id=session_id,
            report=report,
            lease=lease,
        )


def load_report(
    session_id,
):

    with SessionLocal() as db:

        return ReportRepository(
            db
        ).get_for_session(
            session_id
        )


def report_counts(
    session_id,
):

    with SessionLocal() as db:

        row = db.execute(
            text(
                """
                SELECT
                    (
                        SELECT COUNT(*)
                        FROM dbo.research_reports
                        WHERE research_session_id = :session_id
                    ) AS reports,

                    (
                        SELECT COUNT(*)
                        FROM dbo.report_sections AS rs
                        INNER JOIN dbo.research_reports AS rr
                            ON rr.id = rs.research_report_id
                        WHERE rr.research_session_id = :session_id
                    ) AS sections,

                    (
                        SELECT COUNT(*)
                        FROM dbo.report_section_claims AS rsc
                        INNER JOIN dbo.report_sections AS rs
                            ON rs.id = rsc.report_section_id
                        INNER JOIN dbo.research_reports AS rr
                            ON rr.id = rs.research_report_id
                        WHERE rr.research_session_id = :session_id
                    ) AS claims,

                    (
                        SELECT COUNT(*)
                        FROM dbo.report_limitations AS rl
                        INNER JOIN dbo.research_reports AS rr
                            ON rr.id = rl.research_report_id
                        WHERE rr.research_session_id = :session_id
                    ) AS limitations
                """
            ),
            {
                "session_id": session_id,
            },
        ).one()

        return tuple(row)


def delete_review_fixture(
    question_id,
):

    with SessionLocal() as db:

        try:

            db.execute(
                text(
                    """
                    DELETE FROM dbo.reviewed_claims
                    WHERE question_review_id IN (
                        SELECT id
                        FROM dbo.question_reviews
                        WHERE research_question_id = :question_id
                    )
                    """
                ),
                {
                    "question_id": question_id,
                },
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.question_reviews
                    WHERE research_question_id = :question_id
                    """
                ),
                {
                    "question_id": question_id,
                },
            )

            db.commit()

        except Exception:

            db.rollback()

            raise


def main():

    print()
    print("REPORT PROVENANCE AND ROLLBACK")
    print("==============================")

    sessions = []
    review_questions = {}

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
                "reporting",
            )

        question_a, claims_a = (
            create_reviewed_claims(
                session_a
            )
        )

        review_questions[session_a] = question_a

        question_b, claims_b = (
            create_reviewed_claims(
                session_b
            )
        )

        review_questions[session_b] = question_b

        question_c, claims_c = (
            create_reviewed_claims(
                session_c
            )
        )

        review_questions[session_c] = question_c

        lease_a = acquire_lease(
            session_a
        )

        lease_b = acquire_lease(
            session_b
        )

        lease_c = acquire_lease(
            session_c
        )

        #
        # Persist valid reviewed-claim provenance.
        #

        report_a = make_report(
            claims_a
        )

        report_id_a = persist_report(
            session_a,
            report_a,
            lease_a,
        )

        persisted_a = load_report(
            session_a
        )

        assert persisted_a.id == report_id_a

        print(
            "TEST 1 - Valid provenance persisted: PASSED"
        )

        #
        # Duplicate claim IDs must be removed
        # within each section.
        #

        assert (
            persisted_a.sections[0].reviewed_claim_ids
            == sorted(
                [claims_a[0], claims_a[1]]
            )
        )

        assert (
            persisted_a.sections[1].reviewed_claim_ids
            == sorted(
                [claims_a[1], claims_a[2]]
            )
        )

        print(
            "TEST 2 - Duplicate claim references removed: PASSED"
        )

        #
        # Verify all persisted hierarchy rows.
        #

        assert report_counts(
            session_a
        ) == (
            1,
            2,
            4,
            2,
        )

        print(
            "TEST 3 - Complete provenance hierarchy: PASSED"
        )

        #
        # Reject claims belonging to another
        # research session.
        #

        foreign_report = make_report(
            [
                claims_b[0],
                claims_b[1],
                claims_a[0],
            ]
        )

        try:

            persist_report(
                session_c,
                foreign_report,
                lease_c,
            )

        except ValueError:

            pass

        else:

            raise AssertionError(
                "Foreign reviewed claims were accepted."
            )

        assert report_counts(
            session_c
        ) == (
            0,
            0,
            0,
            0,
        )

        print(
            "TEST 4 - Foreign provenance rejected: PASSED"
        )

        #
        # Inject a failure after the report header
        # has been flushed, during section insertion.
        #

        failure_triggered = False

        with SessionLocal() as db:

            connection = db.connection()

            def fail_section_insert(
                conn,
                cursor,
                statement,
                parameters,
                context,
                executemany,
            ):

                nonlocal failure_triggered

                normalized = (
                    " ".join(
                        statement.lower().split()
                    )
                )

                if (
                    not failure_triggered
                    and "insert into report_sections"
                    in normalized
                ):

                    failure_triggered = True

                    raise RuntimeError(
                        "Injected report persistence failure."
                    )

            event.listen(
                connection,
                "before_cursor_execute",
                fail_section_insert,
            )

            try:

                try:

                    ReportRepository(
                        db
                    ).save_report_fenced(
                        session_id=session_b,
                        report=make_report(
                            claims_b
                        ),
                        lease=lease_b,
                    )

                except RuntimeError as exc:

                    assert (
                        str(exc)
                        == "Injected report persistence failure."
                    )

                else:

                    raise AssertionError(
                        "Injected failure did not occur."
                    )

            finally:

                event.remove(
                    connection,
                    "before_cursor_execute",
                    fail_section_insert,
                )

        assert failure_triggered

        print(
            "TEST 5 - Mid-transaction failure injected: PASSED"
        )

        #
        # The complete report hierarchy must
        # have rolled back.
        #

        assert report_counts(
            session_b
        ) == (
            0,
            0,
            0,
            0,
        )

        assert load_report(
            session_b
        ) is None

        print(
            "TEST 6 - Entire report transaction rolled back: PASSED"
        )

        #
        # The same valid lease should be able
        # to retry after rollback.
        #

        report_id_b = persist_report(
            session_b,
            make_report(
                claims_b
            ),
            lease_b,
        )

        assert load_report(
            session_b
        ).id == report_id_b

        assert report_counts(
            session_b
        ) == (
            1,
            2,
            4,
            2,
        )

        print(
            "TEST 7 - Retry after rollback succeeds: PASSED"
        )

        #
        # Verify session isolation.
        #

        assert report_counts(
            session_a
        ) == (
            1,
            2,
            4,
            2,
        )

        assert report_counts(
            session_c
        ) == (
            0,
            0,
            0,
            0,
        )

        print(
            "TEST 8 - Session isolation preserved: PASSED"
        )

        print()
        print("PASS")

    finally:

        for session_id in reversed(
            sessions
        ):

            delete_report(
                session_id
            )

            if session_id in review_questions:

                delete_review_fixture(
                    review_questions[session_id]
                )

            delete_session(
                session_id
            )


if __name__ == "__main__":

    main()
