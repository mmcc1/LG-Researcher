#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
    Index,
    text,
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


    
class UserAccount(Base):

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    email: Mapped[str | None] = mapped_column(
        String(320),
        nullable=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",
    )

    approval_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
    )

    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    email_reports_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


class ResearchJob(Base):

    __tablename__ = "research_jobs"

    __table_args__ = (
        Index(
            "ux_research_jobs_session",
            "research_session_id",
            unique=True,
            mssql_where=text(
                "research_session_id IS NOT NULL"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    research_session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("research_sessions.id"),
        nullable=True,
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
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        index=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    execution_owner: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    lease_version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )


class ResearchJobQuestion(Base):

    __tablename__ = "research_job_questions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    research_job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("research_jobs.id"),
        nullable=False,
        index=True,
    )

    question: Mapped[str] = mapped_column(
        String(2000),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )



class UserSession(Base):

    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )

    csrf_token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )


class PasswordResetRequest(Base):

    __tablename__ = "password_reset_requests"

    __table_args__ = (
        Index(
            "ux_password_reset_requests_pending",
            "user_id",
            unique=True,
            mssql_where=text(
                "status = 'pending'"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    reviewed_by: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
    )

    recovery_code_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    recovery_code_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    failed_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )


class AdminAuditLog(Base):

    __tablename__ = "admin_audit_log"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
    )

    actor_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    target_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    target_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )
