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

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from domain.report import ReportSection
from domain.report_plan import PlannedReportSection

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)

from persistence.models import (
    ReportGeneratedSectionEntity,
    ReportGeneratedSectionClaim,
    ReportPlanEntity,
    ReportPlannedSectionEntity,
    ReportPlannedSectionClaim,
    ResearchSession,
)

from processing.report_section_validator import (
    ReportSectionValidator,
)


@dataclass(frozen=True)
class PersistedGeneratedSection:

    id: int
    ordinal: int
    heading: str
    content: str
    actual_word_count: int
    reviewed_claim_ids: list[int]


class ReportGeneratedSectionRepository:

    def __init__(
        self,
        db: Session,
    ):

        self.db = db

    def _get_plan_entity(
        self,
        session_id: str,
    ) -> ReportPlanEntity | None:

        return (
            self.db.query(
                ReportPlanEntity
            )
            .filter(
                ReportPlanEntity.research_session_id
                == session_id
            )
            .first()
        )

    def _get_planned_section_entity(
        self,
        session_id: str,
        ordinal: int,
    ) -> ReportPlannedSectionEntity | None:

        return (
            self.db.query(
                ReportPlannedSectionEntity
            )
            .join(
                ReportPlanEntity,
                ReportPlannedSectionEntity.report_plan_id
                == ReportPlanEntity.id,
            )
            .filter(
                ReportPlanEntity.research_session_id
                == session_id,
                ReportPlannedSectionEntity.ordinal
                == ordinal,
            )
            .first()
        )

    def _get_allocated_claim_ids(
        self,
        planned_section_id: int,
    ) -> set[int]:

        rows = (
            self.db.query(
                ReportPlannedSectionClaim.reviewed_claim_id
            )
            .filter(
                ReportPlannedSectionClaim.report_planned_section_id
                == planned_section_id
            )
            .all()
        )

        return {
            row[0]
            for row in rows
        }

    def _get_generated_claim_ids(
        self,
        generated_section_id: int,
    ) -> set[int]:

        rows = (
            self.db.query(
                ReportGeneratedSectionClaim.reviewed_claim_id
            )
            .filter(
                ReportGeneratedSectionClaim.report_generated_section_id
                == generated_section_id
            )
            .all()
        )

        return {
            row[0]
            for row in rows
        }

    def get_next_pending_section(
        self,
        session_id: str,
    ) -> PlannedReportSection | None:

        plan_entity = self._get_plan_entity(
            session_id
        )

        if plan_entity is None:

            return None

        planned_sections = (
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

        generated_ids = {
            row[0]
            for row in (
                self.db.query(
                    ReportGeneratedSectionEntity.report_planned_section_id
                )
                .join(
                    ReportPlannedSectionEntity,
                    ReportGeneratedSectionEntity.report_planned_section_id
                    == ReportPlannedSectionEntity.id,
                )
                .filter(
                    ReportPlannedSectionEntity.report_plan_id
                    == plan_entity.id
                )
                .all()
            )
        }

        for planned_section in planned_sections:

            if planned_section.id in generated_ids:

                continue

            allocated_claim_ids = (
                self._get_allocated_claim_ids(
                    planned_section.id
                )
            )

            return PlannedReportSection(
                ordinal=planned_section.ordinal,
                heading=planned_section.heading,
                purpose=planned_section.purpose,
                target_word_count=(
                    planned_section.target_word_count
                ),
                reviewed_claim_ids=sorted(
                    allocated_claim_ids
                ),
            )

        return None

    def get_generated_sections(
        self,
        session_id: str,
    ) -> list[PersistedGeneratedSection]:

        rows = (
            self.db.query(
                ReportGeneratedSectionEntity,
                ReportPlannedSectionEntity,
            )
            .join(
                ReportPlannedSectionEntity,
                ReportGeneratedSectionEntity.report_planned_section_id
                == ReportPlannedSectionEntity.id,
            )
            .join(
                ReportPlanEntity,
                ReportPlannedSectionEntity.report_plan_id
                == ReportPlanEntity.id,
            )
            .filter(
                ReportPlanEntity.research_session_id
                == session_id
            )
            .order_by(
                ReportPlannedSectionEntity.ordinal
            )
            .all()
        )

        results = []

        for generated, planned in rows:

            claim_ids = self._get_generated_claim_ids(
                generated.id
            )

            results.append(
                PersistedGeneratedSection(
                    id=generated.id,
                    ordinal=planned.ordinal,
                    heading=generated.heading,
                    content=generated.content,
                    actual_word_count=(
                        generated.actual_word_count
                    ),
                    reviewed_claim_ids=sorted(
                        claim_ids
                    ),
                )
            )

        return results

    def save_section_fenced(
        self,
        session_id: str,
        ordinal: int,
        section: ReportSection,
        lease: ExecutionLease,
    ) -> int:

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
                    "Generated sections can only be saved "
                    "while the session is reporting."
                )

            planned = self._get_planned_section_entity(
                session_id=session_id,
                ordinal=ordinal,
            )

            if planned is None:

                raise ValueError(
                    "Planned report section not found."
                )

            if section.heading != planned.heading:

                raise ValueError(
                    "Generated section heading differs "
                    "from the persisted plan."
                )

            if not section.content.strip():

                raise ValueError(
                    "Generated section content is empty."
                )

            requested_claim_ids = (
                section.reviewed_claim_ids
            )

            requested_claim_set = set(
                requested_claim_ids
            )

            if len(requested_claim_ids) != len(
                requested_claim_set
            ):

                raise ValueError(
                    "Generated section contains "
                    "duplicate reviewed claim IDs."
                )

            allocated_claim_ids = (
                self._get_allocated_claim_ids(
                    planned.id
                )
            )

            invalid_claim_ids = (
                requested_claim_set
                - allocated_claim_ids
            )

            if invalid_claim_ids:

                invalid_text = ", ".join(
                    str(claim_id)
                    for claim_id in sorted(
                        invalid_claim_ids
                    )
                )

                raise ValueError(
                    "Generated section references "
                    "unallocated reviewed claims: "
                    f"{invalid_text}"
                )

            section_validator = ReportSectionValidator()

            actual_word_count = (
                section_validator.count_words(
                    section.content
                )
            )

            existing = (
                self.db.query(
                    ReportGeneratedSectionEntity
                )
                .filter(
                    ReportGeneratedSectionEntity.report_planned_section_id
                    == planned.id
                )
                .first()
            )

            if existing is not None:

                existing_claim_ids = (
                    self._get_generated_claim_ids(
                        existing.id
                    )
                )

                identical = (
                    existing.heading == section.heading
                    and existing.content == section.content
                    and existing.actual_word_count
                    == actual_word_count
                    and existing_claim_ids
                    == requested_claim_set
                )

                if not identical:

                    raise ValueError(
                        "Generated section differs from "
                        "the previously saved section."
                    )

                section_id = existing.id

                self.db.commit()

                return section_id

            generated = ReportGeneratedSectionEntity(
                report_planned_section_id=planned.id,
                heading=section.heading,
                content=section.content,
                actual_word_count=actual_word_count,
                created_at=datetime.now(
                    timezone.utc
                ),
            )

            self.db.add(
                generated
            )

            self.db.flush()

            for claim_id in sorted(
                requested_claim_set
            ):

                self.db.add(
                    ReportGeneratedSectionClaim(
                        report_generated_section_id=(
                            generated.id
                        ),
                        reviewed_claim_id=claim_id,
                    )
                )

            self.db.flush()

            section_id = generated.id

            self.db.commit()

            return section_id

        except Exception:

            self.db.rollback()

            raise
