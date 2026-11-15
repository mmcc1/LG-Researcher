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

from datetime import datetime, timezone

from sqlalchemy import select

from sqlalchemy.orm import Session

from domain.report_synthesis import (
    ReportSynthesis,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)

from persistence.models import (
    ResearchSession,
    ReportPlanEntity,
    ReportPlannedSectionEntity,
    ReportGeneratedSectionEntity,
    ReportSynthesisEntity,
    ReportSynthesisLimitation,
)

from processing.report_synthesis_validator import (
    ReportSynthesisValidator,
)


class ReportSynthesisRepository:

    def __init__(
        self,
        db: Session,
    ):

        self.db = db

        self.lease_repository = (
            ExecutionLeaseRepository(
                db
            )
        )

        self.validator = (
            ReportSynthesisValidator()
        )


    def _get_plan(
        self,
        session_id: str,
    ) -> ReportPlanEntity | None:

        statement = (
            select(
                ReportPlanEntity
            )
            .where(
                ReportPlanEntity.research_session_id
                == session_id
            )
        )

        return self.db.execute(
            statement
        ).scalar_one_or_none()


    def _get_synthesis_entity(
        self,
        plan_id: int,
    ) -> ReportSynthesisEntity | None:

        statement = (
            select(
                ReportSynthesisEntity
            )
            .where(
                ReportSynthesisEntity.report_plan_id
                == plan_id
            )
        )

        return self.db.execute(
            statement
        ).scalar_one_or_none()


    def _get_limitations(
        self,
        synthesis_id: int,
    ) -> list[str]:

        statement = (
            select(
                ReportSynthesisLimitation
            )
            .where(
                ReportSynthesisLimitation.report_synthesis_id
                == synthesis_id
            )
            .order_by(
                ReportSynthesisLimitation.ordinal
            )
        )

        limitations = self.db.execute(
            statement
        ).scalars().all()

        return [
            limitation.description
            for limitation in limitations
        ]


    def _get_generated_section_ordinals(
        self,
        plan_id: int,
    ) -> tuple[list[int], list[int]]:

        planned_statement = (
            select(
                ReportPlannedSectionEntity.ordinal
            )
            .where(
                ReportPlannedSectionEntity.report_plan_id
                == plan_id
            )
            .order_by(
                ReportPlannedSectionEntity.ordinal
            )
        )

        planned_ordinals = list(
            self.db.execute(
                planned_statement
            ).scalars().all()
        )

        generated_statement = (
            select(
                ReportPlannedSectionEntity.ordinal
            )
            .join(
                ReportGeneratedSectionEntity,
                ReportGeneratedSectionEntity.report_planned_section_id
                == ReportPlannedSectionEntity.id,
            )
            .where(
                ReportPlannedSectionEntity.report_plan_id
                == plan_id
            )
            .order_by(
                ReportPlannedSectionEntity.ordinal
            )
        )

        generated_ordinals = list(
            self.db.execute(
                generated_statement
            ).scalars().all()
        )

        return (
            planned_ordinals,
            generated_ordinals,
        )


    def _validate_sections_complete(
        self,
        plan_id: int,
    ) -> None:

        planned_ordinals, generated_ordinals = (
            self._get_generated_section_ordinals(
                plan_id
            )
        )

        if not planned_ordinals:

            raise ValueError(
                "Cannot persist report synthesis "
                "without planned report sections."
            )

        if planned_ordinals != generated_ordinals:

            missing_ordinals = sorted(
                set(planned_ordinals)
                - set(generated_ordinals)
            )

            raise ValueError(
                "Cannot persist report synthesis "
                "while planned sections remain "
                "unfinished. Missing section ordinals: "
                f"{missing_ordinals}"
            )


    def exists_for_session(
        self,
        session_id: str,
    ) -> bool:

        plan = self._get_plan(
            session_id
        )

        if plan is None:

            return False

        synthesis = self._get_synthesis_entity(
            plan.id
        )

        return synthesis is not None


    def get_for_session(
        self,
        session_id: str,
    ) -> ReportSynthesis | None:

        plan = self._get_plan(
            session_id
        )

        if plan is None:

            return None

        synthesis = self._get_synthesis_entity(
            plan.id
        )

        if synthesis is None:

            return None

        limitations = self._get_limitations(
            synthesis.id
        )

        return ReportSynthesis(
            executive_summary=(
                synthesis.executive_summary
            ),
            conclusions=(
                synthesis.conclusions
            ),
            limitations=limitations,
        )


    def save_synthesis_fenced(
        self,
        session_id: str,
        synthesis: ReportSynthesis,
        lease: ExecutionLease,
    ) -> int:

        if lease.session_id != session_id:

            raise ValueError(
                "Execution lease belongs to "
                "a different research session."
            )

        try:

            self.lease_repository.fence(
                lease
            )

            research_session = self.db.get(
                ResearchSession,
                session_id,
                populate_existing=True,
            )

            if research_session is None:

                raise ValueError(
                    "Research session was not found."
                )

            if research_session.status != "reporting":

                raise ValueError(
                    "Research session must be in "
                    "reporting status to save synthesis."
                )

            plan = self._get_plan(
                session_id
            )

            if plan is None:

                raise ValueError(
                    "Cannot save synthesis without "
                    "a persisted report plan."
                )

            self._validate_sections_complete(
                plan.id
            )

            if not synthesis.executive_summary.strip():

                raise ValueError(
                    "Report executive summary is empty."
                )

            if not synthesis.conclusions.strip():

                raise ValueError(
                    "Report conclusions are empty."
                )

            for limitation in synthesis.limitations:

                if not limitation.strip():

                    raise ValueError(
                        "Report contains an empty limitation."
                    )

            existing = self._get_synthesis_entity(
                plan.id
            )

            if existing is not None:

                existing_limitations = (
                    self._get_limitations(
                        existing.id
                    )
                )

                matches = (
                    existing.executive_summary
                    == synthesis.executive_summary
                    and existing.conclusions
                    == synthesis.conclusions
                    and existing_limitations
                    == synthesis.limitations
                )

                if not matches:

                    raise ValueError(
                        "A different report synthesis "
                        "has already been persisted "
                        "for this report plan."
                    )

                existing_id = existing.id

                self.db.commit()

                return existing_id

            synthesis_entity = ReportSynthesisEntity(
                report_plan_id=plan.id,
                executive_summary=(
                    synthesis.executive_summary
                ),
                conclusions=(
                    synthesis.conclusions
                ),
                created_at=(
                    datetime.now(
                        timezone.utc
                    ).replace(
                        tzinfo=None
                    )
                ),
            )

            self.db.add(
                synthesis_entity
            )

            self.db.flush()

            for ordinal, description in enumerate(
                synthesis.limitations,
                start=1,
            ):

                limitation_entity = (
                    ReportSynthesisLimitation(
                        report_synthesis_id=(
                            synthesis_entity.id
                        ),
                        ordinal=ordinal,
                        description=description,
                    )
                )

                self.db.add(
                    limitation_entity
                )

            synthesis_id = synthesis_entity.id

            self.db.commit()

            return synthesis_id

        except Exception:

            self.db.rollback()

            raise
