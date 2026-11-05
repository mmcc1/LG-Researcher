from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from persistence.database import Base


class ResearchSession(Base):

    __tablename__ = "research_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    topic: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    scope: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    pause_requested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    execution_owner: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    execution_lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    execution_lease_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    questions: Mapped[list["ResearchQuestion"]] = relationship(
        back_populates="research_session",
        cascade="all, delete-orphan",
    )


class ResearchQuestion(Base):

    __tablename__ = "research_questions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    research_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("research_sessions.id"),
        nullable=False,
        index=True,
    )

    category: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    question: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )

    rationale: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    research_session: Mapped["ResearchSession"] = relationship(
        back_populates="questions"
    )


#
# Search attempts.
#
# A search attempt represents one deliberate discovery pass
# for a research question.
#
# Initial research creates an "initial" attempt.
# Later control operations may create additional attempts such
# as "deeper_research" or "counter_evidence".
#
# Search results will be associated with attempts in a later
# stage. For now this entity establishes the durable lifecycle
# of an individual discovery pass.
#


class SearchAttempt(Base):

    __tablename__ = "search_attempts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    research_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("research_sessions.id"),
        nullable=False,
        index=True,
    )

    research_question_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("research_questions.id"),
        nullable=False,
        index=True,
    )

    purpose: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    instructions: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


class WebSearchResult(Base):

    __tablename__ = "web_search_results"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    research_session_id: Mapped[str] = (
        mapped_column(
            String(36),
            ForeignKey("research_sessions.id"),
            nullable=False,
            index=True,
        )
    )

    research_question_id: Mapped[int] = (
        mapped_column(
            Integer,
            ForeignKey("research_questions.id"),
            nullable=False,
            index=True,
        )
    )

    search_attempt_id: Mapped[int | None] = (
        mapped_column(
            Integer,
            ForeignKey("search_attempts.id"),
            nullable=True,
            index=True,
        )
    )

    query: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )

    provider: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    url: Mapped[str] = mapped_column(
        String(4000),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )

    snippet: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )


class Source(Base):

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    research_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("research_sessions.id"),
        nullable=False,
        index=True,
    )

    research_question_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("research_questions.id"),
        nullable=False,
        index=True,
    )

    requested_url: Mapped[str] = mapped_column(
        String(4000),
        nullable=False,
    )

    final_url: Mapped[str] = mapped_column(
        String(4000),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    status_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    raw_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    extracted_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )


class SourceSummary(Base):

    __tablename__ = "source_summaries"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sources.id"),
        nullable=False,
        index=True,
    )

    research_question_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("research_questions.id"),
        nullable=False,
        index=True,
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )


class Finding(Base):

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sources.id"),
        nullable=False,
        index=True,
    )

    research_question_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("research_questions.id"),
        nullable=False,
        index=True,
    )

    claim: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    evidence: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    relevance: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    confidence: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )


class QuestionReview(Base):

    __tablename__ = "question_reviews"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    research_question_id: Mapped[int] = (
        mapped_column(
            Integer,
            ForeignKey(
                "research_questions.id"
            ),
            nullable=False,
            index=True,
        )
    )

    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    overall_confidence: Mapped[str] = (
        mapped_column(
            String(20),
            nullable=False,
        )
    )

    sufficient_evidence: Mapped[bool] = (
        mapped_column(
            Boolean,
            nullable=False,
        )
    )

    created_at: Mapped[datetime] = (
        mapped_column(
            DateTime,
            nullable=False,
        )
    )


class ReviewedClaimEntity(Base):

    __tablename__ = "reviewed_claims"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    question_review_id: Mapped[int] = (
        mapped_column(
            Integer,
            ForeignKey(
                "question_reviews.id"
            ),
            nullable=False,
            index=True,
        )
    )

    claim: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    confidence: Mapped[str] = (
        mapped_column(
            String(20),
            nullable=False,
        )
    )


class ReviewedClaimSupport(Base):

    __tablename__ = (
        "reviewed_claim_support"
    )

    reviewed_claim_id: Mapped[int] = (
        mapped_column(
            Integer,
            ForeignKey(
                "reviewed_claims.id"
            ),
            primary_key=True,
        )
    )

    finding_id: Mapped[int] = (
        mapped_column(
            Integer,
            ForeignKey(
                "findings.id"
            ),
            primary_key=True,
        )
    )


class ReviewedClaimContradiction(Base):

    __tablename__ = (
        "reviewed_claim_contradictions"
    )

    reviewed_claim_id: Mapped[int] = (
        mapped_column(
            Integer,
            ForeignKey(
                "reviewed_claims.id"
            ),
            primary_key=True,
        )
    )

    finding_id: Mapped[int] = (
        mapped_column(
            Integer,
            ForeignKey(
                "findings.id"
            ),
            primary_key=True,
        )
    )


class ReviewContradiction(Base):

    __tablename__ = "review_contradictions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    question_review_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("question_reviews.id"),
        nullable=False,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )


class ReviewEvidenceGap(Base):

    __tablename__ = "review_evidence_gaps"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    question_review_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("question_reviews.id"),
        nullable=False,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )


#
# Final research report.
#
# One final report belongs to one research session.
# Report sections contain the narrative, while
# ReportSectionClaim preserves provenance back to
# reviewed claims.
#


class ResearchReportEntity(Base):

    __tablename__ = "research_reports"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    research_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("research_sessions.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )

    executive_summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    conclusions: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )


class ReportSectionEntity(Base):

    __tablename__ = "report_sections"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    research_report_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("research_reports.id"),
        nullable=False,
        index=True,
    )

    ordinal: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    heading: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )


class ReportSectionClaim(Base):

    __tablename__ = "report_section_claims"

    report_section_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("report_sections.id"),
        primary_key=True,
    )

    reviewed_claim_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("reviewed_claims.id"),
        primary_key=True,
    )


class ReportLimitation(Base):

    __tablename__ = "report_limitations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    research_report_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("research_reports.id"),
        nullable=False,
        index=True,
    )

    ordinal: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )