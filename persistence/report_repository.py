from datetime import datetime, timezone

from sqlalchemy.orm import Session

from domain.report import (
    ResearchReport,
    PersistedResearchReport,
    PersistedReportSection,
)

from persistence.models import (
    ResearchQuestion,
    QuestionReview,
    ReviewedClaimEntity,
    ResearchReportEntity,
    ReportSectionEntity,
    ReportSectionClaim,
    ReportLimitation,
)

from sqlalchemy import text

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)


class ReportRepository:

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def exists_for_session(
        self,
        session_id: str,
    ) -> bool:

        return (
            self.db.query(
                ResearchReportEntity
            )
            .filter(
                ResearchReportEntity.research_session_id
                == session_id
            )
            .first()
            is not None
        )

    def save(
        self,
        session_id: str,
        report: ResearchReport,
        *,
        _commit: bool = True,
    ) -> ResearchReportEntity:

        #
        # Derive the reviewed claims that belong
        # to this research session directly from
        # the database.
        #
        # The caller cannot authorize claim IDs.
        #

        valid_reviewed_claim_ids = (
            self._get_reviewed_claim_ids_for_session(
                session_id
            )
        )

        #
        # Validate all report provenance before
        # adding anything to the SQLAlchemy
        # session.
        #

        self._validate_claim_references(
            report=report,
            valid_reviewed_claim_ids=(
                valid_reviewed_claim_ids
            ),
        )

        #
        # Prevent accidental duplicate reports.
        #
        # research_reports.research_session_id
        # also has a UNIQUE constraint, providing
        # database-level protection.
        #

        if self.exists_for_session(
            session_id
        ):

            raise ValueError(
                "A research report already exists "
                f"for session {session_id}."
            )

        report_entity = (
            ResearchReportEntity(
                research_session_id=session_id,
                title=report.title,
                executive_summary=(
                    report.executive_summary
                ),
                conclusions=(
                    report.conclusions
                ),
                created_at=datetime.now(
                    timezone.utc
                ),
            )
        )

        try:

            self.db.add(
                report_entity
            )

            #
            # Obtain the report identity without
            # committing the transaction.
            #

            self.db.flush()

            #
            # Persist sections in the same order
            # produced by the Report Agent.
            #

            for section_ordinal, section in enumerate(
                report.sections,
                start=1,
            ):

                section_entity = (
                    ReportSectionEntity(
                        research_report_id=(
                            report_entity.id
                        ),
                        ordinal=(
                            section_ordinal
                        ),
                        heading=(
                            section.heading
                        ),
                        content=(
                            section.content
                        ),
                    )
                )

                self.db.add(
                    section_entity
                )

                #
                # Obtain the section identity so
                # its provenance rows can refer
                # to it.
                #

                self.db.flush()

                #
                # Remove duplicate claim IDs while
                # preserving their original order.
                #

                claim_ids = list(
                    dict.fromkeys(
                        section.reviewed_claim_ids
                    )
                )

                for claim_id in claim_ids:

                    self.db.add(
                        ReportSectionClaim(
                            report_section_id=(
                                section_entity.id
                            ),
                            reviewed_claim_id=(
                                claim_id
                            ),
                        )
                    )

            #
            # Persist limitations in deterministic
            # report order.
            #

            for (
                limitation_ordinal,
                limitation,
            ) in enumerate(
                report.limitations,
                start=1,
            ):

                self.db.add(
                    ReportLimitation(
                        research_report_id=(
                            report_entity.id
                        ),
                        ordinal=(
                            limitation_ordinal
                        ),
                        description=(
                            limitation
                        ),
                    )
                )

            #
            # The report, sections, provenance
            # links, and limitations are one
            # transaction.
            #

            self.db.flush()

            if _commit:

                self.db.commit()

                self.db.refresh(
                    report_entity
                )

            return report_entity

        except Exception:

            self.db.rollback()
            raise



    def get_for_session(
        self,
        session_id: str,
    ) -> PersistedResearchReport | None:

        #
        # Load the report belonging to the
        # research session.
        #

        report_entity = (
            self.db.query(
                ResearchReportEntity
            )
            .filter(
                ResearchReportEntity.research_session_id
                == session_id
            )
            .first()
        )

        if report_entity is None:

            return None

        #
        # Load report sections in their original
        # presentation order.
        #

        section_entities = (
            self.db.query(
                ReportSectionEntity
            )
            .filter(
                ReportSectionEntity.research_report_id
                == report_entity.id
            )
            .order_by(
                ReportSectionEntity.ordinal,
                ReportSectionEntity.id,
            )
            .all()
        )

        sections = []

        for section_entity in (
            section_entities
        ):

            #
            # Reconstruct the reviewed-claim
            # provenance associated with this
            # section.
            #

            claim_rows = (
                self.db.query(
                    ReportSectionClaim
                )
                .filter(
                    ReportSectionClaim.report_section_id
                    == section_entity.id
                )
                .order_by(
                    ReportSectionClaim.reviewed_claim_id
                )
                .all()
            )

            sections.append(
                PersistedReportSection(
                    id=section_entity.id,
                    ordinal=(
                        section_entity.ordinal
                    ),
                    heading=(
                        section_entity.heading
                    ),
                    content=(
                        section_entity.content
                    ),
                    reviewed_claim_ids=[
                        row.reviewed_claim_id
                        for row in claim_rows
                    ],
                )
            )

        #
        # Reconstruct limitations in their
        # original presentation order.
        #

        limitation_rows = (
            self.db.query(
                ReportLimitation
            )
            .filter(
                ReportLimitation.research_report_id
                == report_entity.id
            )
            .order_by(
                ReportLimitation.ordinal,
                ReportLimitation.id,
            )
            .all()
        )

        return PersistedResearchReport(
            id=report_entity.id,
            research_session_id=(
                report_entity.research_session_id
            ),
            title=(
                report_entity.title
            ),
            executive_summary=(
                report_entity.executive_summary
            ),
            sections=sections,
            conclusions=(
                report_entity.conclusions
            ),
            limitations=[
                row.description
                for row in limitation_rows
            ],
        )

    def _get_reviewed_claim_ids_for_session(
        self,
        session_id: str,
    ) -> set[int]:

        #
        # Follow the complete ownership chain:
        #
        # ReviewedClaimEntity
        #       ↓
        # QuestionReview
        #       ↓
        # ResearchQuestion
        #       ↓
        # ResearchSession
        #
        # Only reviewed claims belonging to the
        # requested research session are returned.
        #

        rows = (
            self.db.query(
                ReviewedClaimEntity.id
            )
            .join(
                QuestionReview,
                ReviewedClaimEntity.question_review_id
                == QuestionReview.id,
            )
            .join(
                ResearchQuestion,
                QuestionReview.research_question_id
                == ResearchQuestion.id,
            )
            .filter(
                ResearchQuestion.research_session_id
                == session_id
            )
            .all()
        )

        return {
            row[0]
            for row in rows
        }

    def _validate_claim_references(
        self,
        report: ResearchReport,
        valid_reviewed_claim_ids: set[int],
    ) -> None:

        #
        # Every provenance reference generated by
        # the Report Agent must refer to a reviewed
        # claim belonging to this research session.
        #

        invalid_ids = set()

        for section in report.sections:

            for claim_id in (
                section.reviewed_claim_ids
            ):

                if (
                    claim_id
                    not in valid_reviewed_claim_ids
                ):

                    invalid_ids.add(
                        claim_id
                    )

        if invalid_ids:

            invalid_text = ", ".join(
                str(value)
                for value
                in sorted(invalid_ids)
            )

            raise ValueError(
                "Report contains reviewed claim "
                "references that do not belong "
                "to this research session: "
                f"{invalid_text}"
            )


    
    def save_report_fenced(
        self,
        session_id: str,
        report: ResearchReport | None,
        lease: ExecutionLease,
    ) -> int:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            #
            # Lock and validate execution ownership
            # before inspecting or modifying the report.
            #

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            session_row = self.db.execute(
                text(
                    """
                    SELECT status
                    FROM dbo.research_sessions
                    WHERE id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            ).first()

            if session_row is None:

                raise ValueError(
                    "Research session not found."
                )

            #
            # Recover an existing durable report
            # without inserting a duplicate.
            #

            existing = (
                self.db.query(
                    ResearchReportEntity
                )
                .filter(
                    ResearchReportEntity.research_session_id
                    == session_id
                )
                .first()
            )

            if existing is not None:

                if session_row.status not in (
                    "reporting",
                    "completed",
                ):

                    raise ValueError(
                        "Existing report has an "
                        "unexpected session status."
                    )

                report_id = existing.id

                self.db.commit()

                return report_id

            if session_row.status != "reporting":

                raise ValueError(
                    "Research session is not "
                    "ready for report persistence."
                )

            if report is None:

                raise ValueError(
                    "A report is required when "
                    "no persisted report exists."
                )

            #
            # The existing save method validates
            # database-owned provenance and inserts
            # the complete report hierarchy.
            #
            # It must not commit independently.
            #

            persisted = self.save(
                session_id=session_id,
                report=report,
                _commit=False,
            )

            report_id = persisted.id

            self.db.flush()

            self.db.commit()

            return report_id

        except Exception:

            self.db.rollback()

            raise
