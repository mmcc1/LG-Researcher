
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from domain.report import (
    ResearchReport,
    ReportSection,
)

from domain.review import (
    ResearchQuestionReview,
    ReviewedClaim,
)

from nodes.generate_report import GenerateReportNode

from persistence.database import engine

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import (
    Finding,
    Source,
)

from persistence.report_repository import (
    ReportRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.review_repository import (
    ReviewRepository,
)

from processing.report_context_builder import (
    ReportContextBuilder,
)

from processing.report_validator import (
    ReportValidator,
)


TEST_DATABASE = "LGResearcher_Test"

EVIDENCE_GAP = (
    "No research findings were available "
    "for this question."
)

SUPPORTED_CLAIM = (
    "The supplied test evidence identifies "
    "a relationship between aerodynamic "
    "loading and structural stress."
)


@pytest.fixture
def test_environment():

    test_url = engine.url.set(
        database=TEST_DATABASE
    )

    if test_url.database != TEST_DATABASE:

        raise RuntimeError(
            "Tests must use LGResearcher_Test."
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

    created_sessions = []

    try:

        yield Session, created_sessions

    finally:

        for session_id in created_sessions:

            cleanup_session(
                Session,
                session_id,
            )

        test_engine.dispose()


def cleanup_session(
    Session,
    session_id,
):

    with Session() as db:

        try:

            params = {
                "session_id": session_id,
            }

            db.execute(
                text(
                    """
                    DELETE rsc
                    FROM dbo.report_section_claims AS rsc
                    INNER JOIN dbo.report_sections AS rs
                        ON rs.id = rsc.report_section_id
                    INNER JOIN dbo.research_reports AS rr
                        ON rr.id = rs.research_report_id
                    WHERE rr.research_session_id = :session_id
                    """
                ),
                params,
            )

            db.execute(
                text(
                    """
                    DELETE rs
                    FROM dbo.report_sections AS rs
                    INNER JOIN dbo.research_reports AS rr
                        ON rr.id = rs.research_report_id
                    WHERE rr.research_session_id = :session_id
                    """
                ),
                params,
            )

            db.execute(
                text(
                    """
                    DELETE rl
                    FROM dbo.report_limitations AS rl
                    INNER JOIN dbo.research_reports AS rr
                        ON rr.id = rl.research_report_id
                    WHERE rr.research_session_id = :session_id
                    """
                ),
                params,
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.research_reports
                    WHERE research_session_id = :session_id
                    """
                ),
                params,
            )

            db.execute(
                text(
                    """
                    DELETE rcs
                    FROM dbo.reviewed_claim_support AS rcs
                    INNER JOIN dbo.reviewed_claims AS rc
                        ON rc.id = rcs.reviewed_claim_id
                    INNER JOIN dbo.question_reviews AS qr
                        ON qr.id = rc.question_review_id
                    INNER JOIN dbo.research_questions AS q
                        ON q.id = qr.research_question_id
                    WHERE q.research_session_id = :session_id
                    """
                ),
                params,
            )

            db.execute(
                text(
                    """
                    DELETE rcc
                    FROM dbo.reviewed_claim_contradictions AS rcc
                    INNER JOIN dbo.reviewed_claims AS rc
                        ON rc.id = rcc.reviewed_claim_id
                    INNER JOIN dbo.question_reviews AS qr
                        ON qr.id = rc.question_review_id
                    INNER JOIN dbo.research_questions AS q
                        ON q.id = qr.research_question_id
                    WHERE q.research_session_id = :session_id
                    """
                ),
                params,
            )

            for table_name in (
                "reviewed_claims",
                "review_contradictions",
                "review_evidence_gaps",
            ):

                db.execute(
                    text(
                        f"""
                        DELETE child
                        FROM dbo.{table_name} AS child
                        INNER JOIN dbo.question_reviews AS qr
                            ON qr.id = child.question_review_id
                        INNER JOIN dbo.research_questions AS q
                            ON q.id = qr.research_question_id
                        WHERE q.research_session_id = :session_id
                        """
                    ),
                    params,
                )

            db.execute(
                text(
                    """
                    DELETE qr
                    FROM dbo.question_reviews AS qr
                    INNER JOIN dbo.research_questions AS q
                        ON q.id = qr.research_question_id
                    WHERE q.research_session_id = :session_id
                    """
                ),
                params,
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.findings
                    WHERE research_question_id IN (
                        SELECT id
                        FROM dbo.research_questions
                        WHERE research_session_id = :session_id
                    )
                    """
                ),
                params,
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.sources
                    WHERE research_session_id = :session_id
                    """
                ),
                params,
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.research_questions
                    WHERE research_session_id = :session_id
                    """
                ),
                params,
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.research_sessions
                    WHERE id = :session_id
                    """
                ),
                params,
            )

            db.commit()

        except Exception:

            db.rollback()
            raise


def create_test_session(
    Session,
    created_sessions,
    mixed_evidence,
):

    with Session() as db:

        session_repository = (
            ResearchSessionRepository(db)
        )

        research_session = (
            session_repository.create(
                topic="Aircraft wing structural loading",
                scope="Reporting integration test",
            )
        )

        session_id = research_session.id

        created_sessions.append(
            session_id
        )

        supported_question = (
            session_repository.add_question(
                session_id=session_id,
                question=(
                    "What does the available evidence "
                    "say about aerodynamic loading?"
                ),
            )
        )

        unsupported_question = (
            session_repository.add_question(
                session_id=session_id,
                question=(
                    "What does the available evidence "
                    "say about long-term material fatigue?"
                ),
            )
        )

        supported_question_id = (
            supported_question.id
        )

        unsupported_question_id = (
            unsupported_question.id
        )

        finding_id = None

        if mixed_evidence:

            now = datetime.now(
                timezone.utc
            )

            source = Source(
                research_session_id=session_id,
                research_question_id=(
                    supported_question_id
                ),
                requested_url=(
                    "https://example.invalid/"
                    "integration-test"
                ),
                final_url=(
                    "https://example.invalid/"
                    "integration-test"
                ),
                title="Synthetic integration evidence",
                content_type="text/plain",
                status_code=200,
                content_hash="a" * 64,
                raw_content=SUPPORTED_CLAIM,
                extracted_text=SUPPORTED_CLAIM,
                created_at=now,
            )

            db.add(source)
            db.flush()

            finding = Finding(
                source_id=source.id,
                research_question_id=(
                    supported_question_id
                ),
                claim=SUPPORTED_CLAIM,
                evidence=SUPPORTED_CLAIM,
                relevance=(
                    "Relevant to aerodynamic "
                    "loading."
                ),
                confidence="medium",
                created_at=now,
            )

            db.add(finding)
            db.commit()

            finding_id = finding.id

        session_repository.set_question_status(
            question_id=supported_question_id,
            status="researched",
        )

        session_repository.set_question_status(
            question_id=unsupported_question_id,
            status="researched",
        )

    return (
        session_id,
        supported_question_id,
        unsupported_question_id,
        finding_id,
    )


def persist_reviews(
    Session,
    session_id,
    supported_question_id,
    unsupported_question_id,
    finding_id,
    lease,
):

    question_ids = [
        supported_question_id,
        unsupported_question_id,
    ]

    for question_id in question_ids:

        with Session() as db:

            session_repository = (
                ResearchSessionRepository(db)
            )

            selected_question = (
                session_repository
                .select_review_question_fenced(
                    session_id=session_id,
                    lease=lease,
                )
            )

            assert selected_question is not None
            assert selected_question.id == question_id

        if (
            question_id == supported_question_id
            and finding_id is not None
        ):

            review = ResearchQuestionReview(
                answer=SUPPORTED_CLAIM,
                reviewed_claims=[
                    ReviewedClaim(
                        claim=SUPPORTED_CLAIM,
                        supporting_finding_ids=[
                            finding_id
                        ],
                        contradicting_finding_ids=[],
                        confidence="medium",
                    )
                ],
                contradictions=[],
                evidence_gaps=[],
                overall_confidence="medium",
                sufficient_evidence=True,
            )

            valid_finding_ids = {
                finding_id
            }

        else:

            review = ResearchQuestionReview(
                answer=(
                    "Insufficient evidence to answer "
                    "the research question."
                ),
                reviewed_claims=[],
                contradictions=[],
                evidence_gaps=[
                    EVIDENCE_GAP
                ],
                overall_confidence="low",
                sufficient_evidence=False,
            )

            valid_finding_ids = set()

        with Session() as db:

            review_repository = (
                ReviewRepository(db)
            )

            review_repository.save_review_fenced(
                session_id=session_id,
                question_id=question_id,
                review=review,
                valid_finding_ids=valid_finding_ids,
                lease=lease,
            )

    with Session() as db:

        session_repository = (
            ResearchSessionRepository(db)
        )

        session_repository.complete_review_fenced(
            session_id=session_id,
            lease=lease,
        )


@pytest.mark.parametrize(
    "mixed_evidence",
    [
        True,
        False,
    ],
    ids=[
        "mixed_evidence",
        "no_evidence",
    ],
)
def test_generate_report_insufficient_evidence(
    test_environment,
    mixed_evidence,
):

    Session, created_sessions = (
        test_environment
    )

    (
        session_id,
        supported_question_id,
        unsupported_question_id,
        finding_id,
    ) = create_test_session(
        Session=Session,
        created_sessions=created_sessions,
        mixed_evidence=mixed_evidence,
    )

    with Session() as db:

        lease_repository = (
            ExecutionLeaseRepository(db)
        )

        lease = lease_repository.acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    persist_reviews(
        Session=Session,
        session_id=session_id,
        supported_question_id=(
            supported_question_id
        ),
        unsupported_question_id=(
            unsupported_question_id
        ),
        finding_id=finding_id,
        lease=lease,
    )

    with Session() as db:

        reviews = ReviewRepository(
            db
        ).get_for_session(
            session_id
        )

        assert len(reviews) == 2

        reviewed_claim_ids = [
            claim.id
            for review in reviews
            for claim in review.reviewed_claims
        ]

    if mixed_evidence:

        assert len(reviewed_claim_ids) == 1

    else:

        assert reviewed_claim_ids == []

    report_agent = Mock()

    def generate_report(
        topic,
        reviewed_evidence,
    ):

        assert topic == (
            "Aircraft wing structural loading"
        )

        assert EVIDENCE_GAP in reviewed_evidence

        assert (
            "SUFFICIENT EVIDENCE: False"
            in reviewed_evidence
        )

        assert (
            "REVIEWED CLAIMS:\nNone"
            in reviewed_evidence
        )

        if mixed_evidence:

            assert SUPPORTED_CLAIM in reviewed_evidence

            assert (
                "SUFFICIENT EVIDENCE: True"
                in reviewed_evidence
            )

            assert (
                f"REVIEWED CLAIM ID: "
                f"{reviewed_claim_ids[0]}"
            ) in reviewed_evidence

            sections = [
                ReportSection(
                    heading="Supported findings",
                    content=SUPPORTED_CLAIM,
                    reviewed_claim_ids=[
                        reviewed_claim_ids[0]
                    ],
                ),
                ReportSection(
                    heading="Evidence limitations",
                    content=(
                        "The available evidence "
                        "does not answer the "
                        "material fatigue question."
                    ),
                    reviewed_claim_ids=[],
                ),
            ]

        else:

            assert (
                "REVIEWED CLAIM ID:"
                not in reviewed_evidence
            )

            sections = [
                ReportSection(
                    heading="Evidence limitations",
                    content=(
                        "The reviewed material "
                        "does not provide sufficient "
                        "evidence to answer the "
                        "research questions."
                    ),
                    reviewed_claim_ids=[],
                ),
            ]

        return ResearchReport(
            title=topic,
            executive_summary=(
                "The available evidence is limited."
            ),
            sections=sections,
            conclusions=(
                "No conclusions can be drawn "
                "about the unanswered questions."
            ),
            limitations=[
                EVIDENCE_GAP
            ],
        )

    report_agent.generate.side_effect = (
        generate_report
    )

    node = GenerateReportNode(
        session_factory=Session,
        report_agent=report_agent,
        context_builder=ReportContextBuilder(),
        validator=ReportValidator(),
    )

    state = {
        "session_id": session_id,
        "topic": (
            "Aircraft wing structural loading"
        ),
    }

    config = {
        "configurable": {
            "execution_lease": lease,
        }
    }

    result = node(
        state=state,
        config=config,
    )

    assert result == {}

    report_agent.generate.assert_called_once()

    with Session() as db:

        report_repository = (
            ReportRepository(db)
        )

        persisted_report = (
            report_repository.get_for_session(
                session_id
            )
        )

        assert persisted_report is not None

        assert persisted_report.limitations == [
            EVIDENCE_GAP
        ]

        assert (
            persisted_report.research_session_id
            == session_id
        )

        original_report_id = (
            persisted_report.id
        )

        if mixed_evidence:

            assert len(
                persisted_report.sections
            ) == 2

            assert (
                persisted_report
                .sections[0]
                .reviewed_claim_ids
            ) == reviewed_claim_ids

            assert (
                persisted_report
                .sections[1]
                .reviewed_claim_ids
            ) == []

        else:

            assert len(
                persisted_report.sections
            ) == 1

            assert (
                persisted_report
                .sections[0]
                .reviewed_claim_ids
            ) == []

    second_result = node(
        state=state,
        config=config,
    )

    assert second_result == {}

    report_agent.generate.assert_called_once()

    with Session() as db:

        report_repository = (
            ReportRepository(db)
        )

        persisted_report = (
            report_repository.get_for_session(
                session_id
            )
        )

        assert persisted_report.id == (
            original_report_id
        )

        report_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM dbo.research_reports
                WHERE research_session_id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

        assert report_count == 1

    with Session() as db:

        lease_repository = (
            ExecutionLeaseRepository(db)
        )

        assert lease_repository.release(
            lease
        ) is True

        replacement_lease = (
            lease_repository.acquire(
                session_id=session_id,
                duration_seconds=120,
            )
        )

        assert (
            replacement_lease.version
            > lease.version
        )

    with Session() as db:

        report_repository = (
            ReportRepository(db)
        )

        with pytest.raises(
            ExecutionLeaseFenceRejected
        ):

            report_repository.save_report_fenced(
                session_id=session_id,
                report=None,
                lease=lease,
            )

    with Session() as db:

        report_repository = (
            ReportRepository(db)
        )

        persisted_report = (
            report_repository.get_for_session(
                session_id
            )
        )

        assert persisted_report.id == (
            original_report_id
        )

        lease_repository = (
            ExecutionLeaseRepository(db)
        )

        assert lease_repository.release(
            replacement_lease
        ) is True
