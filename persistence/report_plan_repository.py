
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from domain.report_plan import (
    ReportPlan,
    PlannedReportSection,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)

from persistence.models import (
    QuestionReview,
    ReportPlanEntity,
    ReportPlannedSectionEntity,
    ReportPlannedSectionClaim,
    ResearchQuestion,
    ResearchSession,
    ReviewedClaimEntity,
)


class ReportPlanRepository:

    def __init__(
        self,
        db: Session,
    ):

        self.db = db

    def get_for_session(
        self,
        session_id: str,
    ) -> ReportPlan | None:

        plan_entity = (
            self.db.query(
                ReportPlanEntity
            )
            .filter(
                ReportPlanEntity.research_session_id
                == session_id
            )
            .first()
        )

        if plan_entity is None:

            return None

        section_entities = (
            self.db.query(
                ReportPlannedSectionEntity
            )
            .filter(
                ReportPlannedSectionEntity.report_plan_id
                == plan_entity.id
            )
            .order_by(
                ReportPlannedSectionEntity.ordinal
            )
            .all()
        )

        sections = []

        for section_entity in section_entities:

            claim_rows = (
                self.db.query(
                    ReportPlannedSectionClaim
                )
                .filter(
                    ReportPlannedSectionClaim.report_planned_section_id
                    == section_entity.id
                )
                .order_by(
                    ReportPlannedSectionClaim.reviewed_claim_id
                )
                .all()
            )

            planned_section = PlannedReportSection(
                ordinal=section_entity.ordinal,
                heading=section_entity.heading,
                purpose=section_entity.purpose,
                target_word_count=(
                    section_entity.target_word_count
                ),
                reviewed_claim_ids=[
                    row.reviewed_claim_id
                    for row in claim_rows
                ],
            )

            sections.append(
                planned_section
            )

        return ReportPlan(
            title=plan_entity.title,
            target_word_count=plan_entity.target_word_count,
            executive_summary_word_count=(
                plan_entity.executive_summary_word_count
            ),
            conclusions_word_count=(
                plan_entity.conclusions_word_count
            ),
            limitations_word_count=(
                plan_entity.limitations_word_count
            ),
            sections=sections,
        )

    def _get_valid_claim_ids(
        self,
        session_id: str,
    ) -> set[int]:

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

    def _validate_plan(
        self,
        session_id: str,
        plan: ReportPlan,
    ) -> None:

        if not plan.sections:

            raise ValueError(
                "Report plan must contain sections."
            )

        ordinals = [
            section.ordinal
            for section in plan.sections
        ]

        expected_ordinals = list(
            range(
                1,
                len(plan.sections) + 1,
            )
        )

        if ordinals != expected_ordinals:

            raise ValueError(
                "Report plan sections must have "
                "consecutive ordinals starting at 1."
            )

        allocated_words = (
            plan.executive_summary_word_count
            + plan.conclusions_word_count
            + plan.limitations_word_count
        )

        for section in plan.sections:

            allocated_words += (
                section.target_word_count
            )

            claim_ids = section.reviewed_claim_ids

            if len(claim_ids) != len(
                set(claim_ids)
            ):

                raise ValueError(
                    "Report plan section contains "
                    "duplicate reviewed claim IDs."
                )

        if allocated_words != plan.target_word_count:

            raise ValueError(
                "Report plan word allocations "
                "do not equal the target word count."
            )

        valid_claim_ids = self._get_valid_claim_ids(
            session_id
        )

        allocated_claim_ids = set()

        for section in plan.sections:

            allocated_claim_ids.update(
                section.reviewed_claim_ids
            )

        invalid_claim_ids = (
            allocated_claim_ids
            - valid_claim_ids
        )

        if invalid_claim_ids:

            invalid_text = ", ".join(
                str(claim_id)
                for claim_id in sorted(
                    invalid_claim_ids
                )
            )

            raise ValueError(
                "Report plan references reviewed claims "
                "outside the research session: "
                f"{invalid_text}"
            )

    def _plans_match(
        self,
        existing: ReportPlan,
        requested: ReportPlan,
    ) -> bool:

        if (
            existing.title
            != requested.title
        ):

            return False

        if (
            existing.target_word_count
            != requested.target_word_count
        ):

            return False

        if (
            existing.executive_summary_word_count
            != requested.executive_summary_word_count
        ):

            return False

        if (
            existing.conclusions_word_count
            != requested.conclusions_word_count
        ):

            return False

        if (
            existing.limitations_word_count
            != requested.limitations_word_count
        ):

            return False

        if len(existing.sections) != len(
            requested.sections
        ):

            return False

        for existing_section, requested_section in zip(
            existing.sections,
            requested.sections,
        ):

            if (
                existing_section.ordinal
                != requested_section.ordinal
            ):

                return False

            if (
                existing_section.heading
                != requested_section.heading
            ):

                return False

            if (
                existing_section.purpose
                != requested_section.purpose
            ):

                return False

            if (
                existing_section.target_word_count
                != requested_section.target_word_count
            ):

                return False

            if sorted(
                existing_section.reviewed_claim_ids
            ) != sorted(
                requested_section.reviewed_claim_ids
            ):

                return False

        return True

    def save_plan_fenced(
        self,
        session_id: str,
        plan: ReportPlan,
        lease: ExecutionLease,
    ) -> None:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            research_session = self.db.get(
                ResearchSession,
                session_id,
                populate_existing=True,
            )

            if research_session is None:

                raise ValueError(
                    "Research session not found."
                )

            if research_session.status != "reporting":

                raise ValueError(
                    "Report plan persistence requires "
                    "a reporting research session."
                )

            existing_plan = self.get_for_session(
                session_id
            )

            if existing_plan is not None:

                if not self._plans_match(
                    existing=existing_plan,
                    requested=plan,
                ):

                    raise ValueError(
                        "Report plan differs from "
                        "the previously saved plan."
                    )

                self.db.commit()

                return

            self._validate_plan(
                session_id=session_id,
                plan=plan,
            )

            now = datetime.now(
                timezone.utc
            )

            plan_entity = ReportPlanEntity(
                research_session_id=session_id,
                title=plan.title,
                target_word_count=plan.target_word_count,
                executive_summary_word_count=(
                    plan.executive_summary_word_count
                ),
                conclusions_word_count=(
                    plan.conclusions_word_count
                ),
                limitations_word_count=(
                    plan.limitations_word_count
                ),
                created_at=now,
            )

            self.db.add(
                plan_entity
            )

            self.db.flush()

            for section in plan.sections:

                section_entity = (
                    ReportPlannedSectionEntity(
                        report_plan_id=plan_entity.id,
                        ordinal=section.ordinal,
                        heading=section.heading,
                        purpose=section.purpose,
                        target_word_count=(
                            section.target_word_count
                        ),
                    )
                )

                self.db.add(
                    section_entity
                )

                self.db.flush()

                for claim_id in section.reviewed_claim_ids:

                    claim_entity = ReportPlannedSectionClaim(
                        report_planned_section_id=(
                            section_entity.id
                        ),
                        reviewed_claim_id=claim_id,
                    )

                    self.db.add(
                        claim_entity
                    )

            self.db.flush()

            self.db.commit()

        except Exception:

            self.db.rollback()

            raise
