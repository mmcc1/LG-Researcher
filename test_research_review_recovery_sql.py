
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from domain.report import (
    ResearchReport,
    ReportSection,
)

from domain.review import (
    ResearchQuestionReview,
)

from persistence.database import engine

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.review_repository import (
    ReviewRepository,
)

from persistence.report_repository import (
    ReportRepository,
)


TEST_DATABASE = "LGResearcher_Test"


@pytest.fixture
def test_environment():

    test_url = engine.url.set(
        database=TEST_DATABASE
    )

    if test_url.database != TEST_DATABASE:

        raise RuntimeError(
            "Invalid integration test database."
        )

    test_engine = create_engine(
        test_url,
        echo=False,
    )

    Session = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    with test_engine.connect() as connection:

        database_name = connection.execute(
            text("SELECT DB_NAME()")
        ).scalar_one()

        if database_name != TEST_DATABASE:

            test_engine.dispose()

            raise RuntimeError(
                "Integration test database mismatch. "
                f"Connected to: {database_name}"
            )

    session_ids = []

    try:

        yield Session, session_ids

    finally:

        with Session() as db:

            for session_id in session_ids:

                params = {
                    "session_id": session_id,
                }

                #
                # Remove report descendants before
                # deleting their parent reports.
                #

                db.execute(
                    text("""
                        DELETE FROM dbo.report_section_claims
                        WHERE report_section_id IN (
                            SELECT rs.id
                            FROM dbo.report_sections rs
                            JOIN dbo.research_reports rr
                                ON rr.id = rs.research_report_id
                            WHERE rr.research_session_id = :session_id
                        )
                    """),
                    params,
                )

                db.execute(
                    text("""
                        DELETE FROM dbo.report_sections
                        WHERE research_report_id IN (
                            SELECT id
                            FROM dbo.research_reports
                            WHERE research_session_id = :session_id
                        )
                    """),
                    params,
                )

                db.execute(
                    text("""
                        DELETE FROM dbo.report_limitations
                        WHERE research_report_id IN (
                            SELECT id
                            FROM dbo.research_reports
                            WHERE research_session_id = :session_id
                        )
                    """),
                    params,
                )

                db.execute(
                    text("""
                        DELETE FROM dbo.research_reports
                        WHERE research_session_id = :session_id
                    """),
                    params,
                )

                #
                # Remove reviewed-claim descendants.
                #

                review_ids = """
                    SELECT qr.id
                    FROM dbo.question_reviews qr
                    JOIN dbo.research_questions rq
                        ON rq.id = qr.research_question_id
                    WHERE rq.research_session_id = :session_id
                """

                claim_ids = f"""
                    SELECT id
                    FROM dbo.reviewed_claims
                    WHERE question_review_id IN (
                        {review_ids}
                    )
                """

                db.execute(
                    text(f"""
                        DELETE FROM dbo.reviewed_claim_support
                        WHERE reviewed_claim_id IN (
                            {claim_ids}
                        )
                    """),
                    params,
                )

                db.execute(
                    text(f"""
                        DELETE FROM dbo.reviewed_claim_contradictions
                        WHERE reviewed_claim_id IN (
                            {claim_ids}
                        )
                    """),
                    params,
                )

                db.execute(
                    text(f"""
                        DELETE FROM dbo.reviewed_claims
                        WHERE question_review_id IN (
                            {review_ids}
                        )
                    """),
                    params,
                )

                db.execute(
                    text(f"""
                        DELETE FROM dbo.review_contradictions
                        WHERE question_review_id IN (
                            {review_ids}
                        )
                    """),
                    params,
                )

                db.execute(
                    text(f"""
                        DELETE FROM dbo.review_evidence_gaps
                        WHERE question_review_id IN (
                            {review_ids}
                        )
                    """),
                    params,
                )

                db.execute(
                    text(f"""
                        DELETE FROM dbo.question_reviews
                        WHERE research_question_id IN (
                            SELECT id
                            FROM dbo.research_questions
                            WHERE research_session_id = :session_id
                        )
                    """),
                    params,
                )

                #
                # These tests create no findings,
                # sources, search attempts, or jobs.
                #

                db.execute(
                    text("""
                        DELETE FROM dbo.research_questions
                        WHERE research_session_id = :session_id
                    """),
                    params,
                )

                db.execute(
                    text("""
                        DELETE FROM dbo.research_sessions
                        WHERE id = :session_id
                    """),
                    params,
                )

            db.commit()

        test_engine.dispose()


def create_recovery_session(
    Session,
    session_ids,
):

    with Session() as db:

        repository = ResearchSessionRepository(
            db
        )

        research_session = repository.create(
            topic="Synthetic recovery assessment",
            scope="SQL integration testing",
        )

        session_id = research_session.id

        session_ids.append(
            session_id
        )

        first_question = repository.add_question(
            session_id=session_id,
            question=(
                "What evidence supports the first "
                "research question?"
            ),
        )

        second_question = repository.add_question(
            session_id=session_id,
            question=(
                "What evidence supports the second "
                "research question?"
            ),
        )

        repository.set_question_status(
            question_id=first_question.id,
            status="reviewing",
        )

        repository.set_question_status(
            question_id=second_question.id,
            status="researched",
        )

        repository.set_status(
            session_id=session_id,
            status="reviewing",
        )

        return (
            session_id,
            first_question.id,
            second_question.id,
        )


def create_insufficient_evidence_review():

    return ResearchQuestionReview(
        answer=(
            "Insufficient evidence to answer "
            "the research question."
        ),
        reviewed_claims=[],
        contradictions=[],
        evidence_gaps=[
            "No research findings were available "
            "for this question."
        ],
        overall_confidence="low",
        sufficient_evidence=False,
    )


def create_insufficient_evidence_report():

    return ResearchReport(
        title="Research Evidence Assessment",
        executive_summary=(
            "The available reviewed material does "
            "not provide sufficient evidence to "
            "establish research conclusions."
        ),
        sections=[
            ReportSection(
                heading="Evidence Gaps",
                content=(
                    "The reviewed questions lack "
                    "supporting findings. No substantive "
                    "conclusions can be established."
                ),
                reviewed_claim_ids=[],
            ),
        ],
        conclusions=(
            "Further research is required before "
            "reliable conclusions can be drawn."
        ),
        limitations=[
            "No supporting research findings were available.",
            "The reviewed questions contain insufficient evidence.",
        ],
    )


def get_question_review_count(
    Session,
    question_id,
):

    with Session() as db:

        return db.execute(
            text("""
                SELECT COUNT(*)
                FROM dbo.question_reviews
                WHERE research_question_id = :question_id
            """),
            {
                "question_id": question_id,
            },
        ).scalar_one()


def get_report_count(
    Session,
    session_id,
):

    with Session() as db:

        return db.execute(
            text("""
                SELECT COUNT(*)
                FROM dbo.research_reports
                WHERE research_session_id = :session_id
            """),
            {
                "session_id": session_id,
            },
        ).scalar_one()


def test_review_recovery_preserves_existing_question(
    test_environment,
):

    Session, session_ids = test_environment

    (
        session_id,
        first_question_id,
        second_question_id,
    ) = create_recovery_session(
        Session,
        session_ids,
    )

    with Session() as db:

        lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

        assert lease is not None

    try:

        with Session() as db:

            repository = ResearchSessionRepository(
                db
            )

            selected = repository.select_review_question_fenced(
                session_id=session_id,
                lease=lease,
            )

            assert selected is not None

            assert selected.id == first_question_id

        with Session() as db:

            repository = ReviewRepository(
                db
            )

            first_review_id = repository.save_review_fenced(
                session_id=session_id,
                question_id=first_question_id,
                review=create_insufficient_evidence_review(),
                valid_finding_ids=set(),
                lease=lease,
            )

            assert first_review_id > 0

        with Session() as db:

            repository = ResearchSessionRepository(
                db
            )

            selected = repository.select_review_question_fenced(
                session_id=session_id,
                lease=lease,
            )

            assert selected is not None

            assert selected.id == second_question_id

        with Session() as db:

            repository = ReviewRepository(
                db
            )

            second_review_id = repository.save_review_fenced(
                session_id=session_id,
                question_id=second_question_id,
                review=create_insufficient_evidence_review(),
                valid_finding_ids=set(),
                lease=lease,
            )

            assert second_review_id > 0

        with Session() as db:

            repository = ResearchSessionRepository(
                db
            )

            selected = repository.select_review_question_fenced(
                session_id=session_id,
                lease=lease,
            )

            assert selected is None

            repository.complete_review_fenced(
                session_id=session_id,
                lease=lease,
            )

            research_session = repository.get(
                session_id
            )

            assert research_session.status == "reviewed"

        assert get_question_review_count(
            Session,
            first_question_id,
        ) == 1

        assert get_question_review_count(
            Session,
            second_question_id,
        ) == 1

    finally:

        with Session() as db:

            ExecutionLeaseRepository(
                db
            ).release(
                lease
            )


def test_existing_review_is_not_duplicated(
    test_environment,
):

    Session, session_ids = test_environment

    (
        session_id,
        first_question_id,
        _,
    ) = create_recovery_session(
        Session,
        session_ids,
    )

    with Session() as db:

        lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

        assert lease is not None

    try:

        with Session() as db:

            repository = ReviewRepository(
                db
            )

            original_id = repository.save_review_fenced(
                session_id=session_id,
                question_id=first_question_id,
                review=create_insufficient_evidence_review(),
                valid_finding_ids=set(),
                lease=lease,
            )

        with Session() as db:

            repository = ReviewRepository(
                db
            )

            recovered_id = repository.save_review_fenced(
                session_id=session_id,
                question_id=first_question_id,
                review=None,
                valid_finding_ids=set(),
                lease=lease,
            )

        assert recovered_id == original_id

        assert get_question_review_count(
            Session,
            first_question_id,
        ) == 1

    finally:

        with Session() as db:

            ExecutionLeaseRepository(
                db
            ).release(
                lease
            )


def test_report_persistence_and_recovery(
    test_environment,
):

    Session, session_ids = test_environment

    (
        session_id,
        first_question_id,
        second_question_id,
    ) = create_recovery_session(
        Session,
        session_ids,
    )

    with Session() as db:

        lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

        assert lease is not None

    try:

        for question_id in (
            first_question_id,
            second_question_id,
        ):

            #
            # Select the question through the normal
            # review lifecycle before saving its review.
            #

            with Session() as db:

                repository = ResearchSessionRepository(
                    db
                )

                selected = repository.select_review_question_fenced(
                    session_id=session_id,
                    lease=lease,
                )

                assert selected is not None

                assert selected.id == question_id

            #
            # The selected question is now reviewing
            # and can receive a persisted review.
            #

            with Session() as db:

                repository = ReviewRepository(
                    db
                )

                repository.save_review_fenced(
                    session_id=session_id,
                    question_id=question_id,
                    review=create_insufficient_evidence_review(),
                    valid_finding_ids=set(),
                    lease=lease,
                )

        with Session() as db:

            repository = ResearchSessionRepository(
                db
            )

            repository.complete_review_fenced(
                session_id=session_id,
                lease=lease,
            )

            repository.begin_reporting_fenced(
                session_id=session_id,
                lease=lease,
            )

        with Session() as db:

            repository = ReportRepository(
                db
            )

            original_report_id = repository.save_report_fenced(
                session_id=session_id,
                report=create_insufficient_evidence_report(),
                lease=lease,
            )

            assert original_report_id > 0

        with Session() as db:

            repository = ReportRepository(
                db
            )

            recovered_report_id = repository.save_report_fenced(
                session_id=session_id,
                report=None,
                lease=lease,
            )

        assert recovered_report_id == original_report_id

        assert get_report_count(
            Session,
            session_id,
        ) == 1

        with Session() as db:

            repository = ReportRepository(
                db
            )

            persisted_report = repository.get_for_session(
                session_id
            )

            assert persisted_report is not None

            assert persisted_report.id == original_report_id

            assert len(persisted_report.sections) == 1

            assert (
                persisted_report.sections[0].reviewed_claim_ids
                == []
            )

            assert len(persisted_report.limitations) == 2

        with Session() as db:

            repository = ResearchSessionRepository(
                db
            )

            repository.complete_report_fenced(
                session_id=session_id,
                lease=lease,
            )

            research_session = repository.get(
                session_id
            )

            assert research_session.status == "completed"

    finally:

        with Session() as db:

            ExecutionLeaseRepository(
                db
            ).release(
                lease
            )
