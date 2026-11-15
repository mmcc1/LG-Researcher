
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from persistence.database import SessionLocal

from persistence.models import (
    ResearchSession,
    ResearchQuestion,
    Source,
    SourceSummary,
    Finding,
    QuestionReview,
    ReviewedClaimEntity,
    ResearchReportEntity,
    ReportSectionEntity,
    ReportLimitation,
)


def create_test_text(label: str) -> str:

    return (
        f"{label}: "
        "Amsterdam — geschiedenis en cultuur. "
        "日本語 中文 한국어. "
        "Mathematics: α β γ ∑ ∞. "
        "Symbols: ✨🐺"
    )


def verify_value(
    db,
    model,
    record_id,
    field_name,
    expected_value,
):

    statement = (
        select(model)
        .where(model.id == record_id)
    )

    record = db.execute(
        statement
    ).scalar_one()

    actual_value = getattr(
        record,
        field_name,
    )

    assert actual_value == expected_value, (
        f"{model.__name__}.{field_name}: "
        "Unicode round-trip mismatch.\n"
        f"Expected: {expected_value!r}\n"
        f"Actual:   {actual_value!r}"
    )

    print(
        f"{model.__name__}.{field_name}: PASSED"
    )


def main():

    print()
    print("UNICODE PERSISTENCE ROUND-TRIP TEST")
    print("===================================")
    print()

    session_id = str(
        uuid4()
    )

    timestamp = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    test_values = {}

    db = SessionLocal()

    try:

        research_session = ResearchSession(
            id=session_id,
            topic=create_test_text("Topic"),
            scope=create_test_text("Scope"),
            status="created",
            pause_requested=False,
            execution_lease_version=0,
            created_at=timestamp,
            updated_at=timestamp,
        )

        db.add(
            research_session
        )

        db.flush()

        research_question = ResearchQuestion(
            research_session_id=session_id,
            category=create_test_text("Category"),
            question=create_test_text("Question"),
            rationale=create_test_text("Rationale"),
            status="pending",
            created_at=timestamp,
            updated_at=timestamp,
        )

        db.add(
            research_question
        )

        db.flush()

        source = Source(
            research_session_id=session_id,
            research_question_id=research_question.id,
            requested_url="https://example.com/unicode-test",
            final_url="https://example.com/unicode-test",
            title=create_test_text("Source title"),
            content_type="text/html",
            status_code=200,
            content_hash=uuid4().hex,
            raw_content=create_test_text("Raw content"),
            extracted_text=create_test_text("Extracted text"),
            created_at=timestamp,
        )

        db.add(
            source
        )

        db.flush()

        source_summary = SourceSummary(
            source_id=source.id,
            research_question_id=research_question.id,
            summary=create_test_text("Source summary"),
            created_at=timestamp,
        )

        db.add(
            source_summary
        )

        finding = Finding(
            source_id=source.id,
            research_question_id=research_question.id,
            claim=create_test_text("Claim"),
            evidence=create_test_text("Evidence"),
            relevance=create_test_text("Relevance"),
            confidence="high",
            created_at=timestamp,
        )

        db.add(
            finding
        )

        question_review = QuestionReview(
            research_question_id=research_question.id,
            answer=create_test_text("Review answer"),
            overall_confidence="high",
            sufficient_evidence=True,
            created_at=timestamp,
        )

        db.add(
            question_review
        )

        db.flush()

        reviewed_claim = ReviewedClaimEntity(
            question_review_id=question_review.id,
            claim=create_test_text("Reviewed claim"),
            confidence="high",
        )

        db.add(
            reviewed_claim
        )

        research_report = ResearchReportEntity(
            research_session_id=session_id,
            title=create_test_text("Report title"),
            executive_summary=create_test_text(
                "Executive summary"
            ),
            conclusions=create_test_text("Conclusions"),
            created_at=timestamp,
        )

        db.add(
            research_report
        )

        db.flush()

        report_section = ReportSectionEntity(
            research_report_id=research_report.id,
            ordinal=1,
            heading=create_test_text("Section heading"),
            content=create_test_text("Section content"),
        )

        db.add(
            report_section
        )

        report_limitation = ReportLimitation(
            research_report_id=research_report.id,
            ordinal=1,
            description=create_test_text(
                "Report limitation"
            ),
        )

        db.add(
            report_limitation
        )

        db.flush()

        records = [
            (
                ResearchSession,
                research_session,
                ["topic", "scope"],
            ),
            (
                ResearchQuestion,
                research_question,
                ["category", "question", "rationale"],
            ),
            (
                Source,
                source,
                [
                    "title",
                    "raw_content",
                    "extracted_text",
                ],
            ),
            (
                SourceSummary,
                source_summary,
                ["summary"],
            ),
            (
                Finding,
                finding,
                ["claim", "evidence", "relevance"],
            ),
            (
                QuestionReview,
                question_review,
                ["answer"],
            ),
            (
                ReviewedClaimEntity,
                reviewed_claim,
                ["claim"],
            ),
            (
                ResearchReportEntity,
                research_report,
                [
                    "title",
                    "executive_summary",
                    "conclusions",
                ],
            ),
            (
                ReportSectionEntity,
                report_section,
                ["heading", "content"],
            ),
            (
                ReportLimitation,
                report_limitation,
                ["description"],
            ),
        ]

        for model, record, field_names in records:

            for field_name in field_names:

                key = (
                    model,
                    record.id,
                    field_name,
                )

                test_values[key] = getattr(
                    record,
                    field_name,
                )

        print(
            "Disposable research records created: PASSED"
        )
        print()

        # Expire ORM objects so verification reloads
        # their values from SQL Server.
        db.expire_all()

        for key, expected_value in test_values.items():

            model, record_id, field_name = key

            verify_value(
                db=db,
                model=model,
                record_id=record_id,
                field_name=field_name,
                expected_value=expected_value,
            )

        print()
        print(
            f"Unicode fields verified: {len(test_values)}"
        )

        print()
        print(
            "Unicode persistence round-trip: PASSED"
        )

    finally:

        # All test inserts remain inside this transaction.
        # Rollback removes them even if verification fails.
        try:

            db.rollback()

            print(
                "Disposable research records rolled back: PASSED"
            )

        finally:

            db.close()


if __name__ == "__main__":
    main()
