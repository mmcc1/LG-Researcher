
#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

from time import perf_counter

from collections.abc import Callable

from sqlalchemy.orm import sessionmaker

from langchain_core.runnables import (
    RunnableConfig,
)

from agents.report_agent import (
    ReportAgent,
)

from agents.report_section_agent import (
    ReportSectionAgent,
)

from agents.report_synthesis_agent import (
    ReportSynthesisAgent,
)

from domain.report import (
    ReportSection,
)

from graph.state import (
    ResearchState,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
)

from persistence.report_repository import (
    ReportRepository,
)

from persistence.report_plan_repository import (
    ReportPlanRepository,
)

from persistence.report_generated_section_repository import (
    ReportGeneratedSectionRepository,
)

from persistence.report_synthesis_repository import (
    ReportSynthesisRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.review_repository import (
    ReviewRepository,
)

from persistence.research_scope_repository import (
    ResearchScopeRepository,
)

from processing.report_context_builder import (
    ReportContextBuilder,
)

from processing.report_section_context_builder import (
    ReportSectionContextBuilder,
)

from processing.report_validator import (
    ReportValidator,
)

from processing.report_assembler import (
    ReportAssembler,
)


class GenerateReportNode:

    def __init__(
        self,
        session_factory: sessionmaker,
        report_agent: ReportAgent,
        context_builder: ReportContextBuilder,
        validator: ReportValidator,
        report_section_agent: ReportSectionAgent,
        report_synthesis_agent: ReportSynthesisAgent,
        section_context_builder: ReportSectionContextBuilder,
        report_assembler: ReportAssembler,
    ):

        self.session_factory = (
            session_factory
        )

        self.report_agent = (
            report_agent
        )

        self.context_builder = (
            context_builder
        )

        self.validator = (
            validator
        )

        self.report_section_agent = (
            report_section_agent
        )

        self.report_synthesis_agent = (
            report_synthesis_agent
        )

        self.section_context_builder = (
            section_context_builder
        )

        self.report_assembler = (
            report_assembler
        )

    def _check_execution(
        self,
        execution_guard: Callable | None,
    ) -> None:

        if execution_guard is not None:

            execution_guard()

    def _get_generated_sections(
        self,
        session_id: str,
    ):

        with self.session_factory() as db:

            repository = (
                ReportGeneratedSectionRepository(
                    db
                )
            )

            return repository.get_generated_sections(
                session_id
            )

    def _build_preceding_context(
        self,
        generated_sections,
        current_ordinal: int,
    ) -> str:

        preceding_sections = [
            section
            for section in generated_sections
            if section.ordinal < current_ordinal
        ]

        if not preceding_sections:

            return ""

        lines = [
            "Previously completed report sections:",
            "",
        ]

        for section in preceding_sections:

            lines.append(
                f"{section.ordinal}. {section.heading}"
            )

        lines.append("")
        lines.append(
            "Avoid unnecessary repetition of these topics."
        )

        return "\n".join(
            lines
        )

    def __call__(
        self,
        state: ResearchState,
        config: RunnableConfig,
    ) -> dict:

        session_id = state[
            "session_id"
        ]

        topic = state[
            "topic"
        ]

        configurable = config.get(
            "configurable",
            {},
        )

        lease = configurable.get(
            "execution_lease"
        )

        if not isinstance(
            lease,
            ExecutionLease,
        ):

            raise RuntimeError(
                "Execution lease is missing "
                "from graph configuration."
            )

        if lease.session_id != session_id:

            raise ValueError(
                "Execution lease does not match "
                "the research session."
            )

        execution_guard = configurable.get(
            "execution_guard"
        )

        if (
            execution_guard is not None
            and not callable(execution_guard)
        ):

            raise TypeError(
                "Execution guard must be callable."
            )

        self._check_execution(
            execution_guard
        )

        #
        # A completed report may already exist if the
        # previous worker stopped before session completion.
        #

        with self.session_factory() as db:

            report_repository = (
                ReportRepository(
                    db
                )
            )

            if report_repository.exists_for_session(
                session_id
            ):

                report_id = (
                    report_repository.save_report_fenced(
                        session_id=session_id,
                        report=None,
                        lease=lease,
                    )
                )

                self._check_execution(
                    execution_guard
                )

                print()
                print(
                    "Research report already exists. "
                    f"Report ID: {report_id}"
                )

                print(
                    "Skipping report generation."
                )

                return {}

        #
        # Research and review must be complete before
        # any report components are generated.
        #

        with self.session_factory() as db:

            session_repository = (
                ResearchSessionRepository(
                    db
                )
            )

            if session_repository.has_unfinished_research_questions(
                session_id
            ):

                raise RuntimeError(
                    "Cannot generate final report "
                    "because one or more research "
                    "questions have not completed "
                    "research."
                )

            if session_repository.has_unfinished_review_questions(
                session_id
            ):

                raise RuntimeError(
                    "Cannot generate final report "
                    "because one or more research "
                    "questions have not completed "
                    "review."
                )

        self._check_execution(
            execution_guard
        )

        with self.session_factory() as db:

            session_repository = (
                ResearchSessionRepository(
                    db
                )
            )

            session_repository.begin_reporting_fenced(
                session_id=session_id,
                lease=lease,
            )

        #
        # Load the persisted reviews and scope once.
        # Database sessions are not held open during
        # model invocations.
        #

        with self.session_factory() as db:

            review_repository = (
                ReviewRepository(
                    db
                )
            )

            scope_repository = (
                ResearchScopeRepository(
                    db
                )
            )

            reviews = review_repository.get_for_session(
                session_id
            )

            scope_definition = scope_repository.get(
                session_id
            )

        if not reviews:

            raise RuntimeError(
                "Cannot generate report because "
                "the research session contains "
                "no persisted reviews."
            )

        reviewed_evidence = (
            self.context_builder.build(
                reviews
            )
        )

        valid_reviewed_claim_ids = {
            claim.id
            for review in reviews
            for claim in review.reviewed_claims
        }

        print()
        print(
            "Generating incremental research report...",
            flush=True,
        )

        print(
            f"Reviews: {len(reviews):,}"
        )

        print(
            "Reviewed claims: "
            f"{len(valid_reviewed_claim_ids):,}"
        )

        print(
            "Report context length: "
            f"{len(reviewed_evidence):,} chars"
        )

        #
        # Recover the persisted plan or generate it.
        #

        with self.session_factory() as db:

            plan_repository = (
                ReportPlanRepository(
                    db
                )
            )

            plan = plan_repository.get_for_session(
                session_id
            )

        if plan is None:

            self._check_execution(
                execution_guard
            )

            print()
            print(
                "Generating report plan...",
                flush=True,
            )

            start = perf_counter()

            plan = self.report_agent.plan(
                topic=topic,
                reviewed_evidence=reviewed_evidence,
                valid_reviewed_claim_ids=(
                    valid_reviewed_claim_ids
                ),
                scope_definition=scope_definition,
            )

            self._check_execution(
                execution_guard
            )

            with self.session_factory() as db:

                plan_repository = (
                    ReportPlanRepository(
                        db
                    )
                )

                plan_repository.save_plan_fenced(
                    session_id=session_id,
                    plan=plan,
                    lease=lease,
                )

            print(
                "Report plan persisted in "
                f"{perf_counter() - start:.1f}s."
            )

        else:

            print()
            print(
                "Recovered persisted report plan."
            )

        print(
            f"Planned sections: {len(plan.sections)}"
        )

        #
        # Generate only sections not already persisted.
        # Each section is committed independently.
        #

        while True:

            self._check_execution(
                execution_guard
            )

            with self.session_factory() as db:

                section_repository = (
                    ReportGeneratedSectionRepository(
                        db
                    )
                )

                pending_section = (
                    section_repository.get_next_pending_section(
                        session_id
                    )
                )

            if pending_section is None:

                break

            generated_sections = (
                self._get_generated_sections(
                    session_id
                )
            )

            preceding_context = (
                self._build_preceding_context(
                    generated_sections=generated_sections,
                    current_ordinal=pending_section.ordinal,
                )
            )

            section_evidence = (
                self.section_context_builder.build(
                    reviews=reviews,
                    section=pending_section,
                )
            )

            print()
            print(
                "Generating report section "
                f"{pending_section.ordinal}: "
                f"{pending_section.heading}",
                flush=True,
            )

            start = perf_counter()

            generated_section = (
                self.report_section_agent.generate(
                    topic=topic,
                    section=pending_section,
                    reviewed_evidence=section_evidence,
                    preceding_context=preceding_context,
                )
            )

            self._check_execution(
                execution_guard
            )

            with self.session_factory() as db:

                section_repository = (
                    ReportGeneratedSectionRepository(
                        db
                    )
                )

                section_repository.save_section_fenced(
                    session_id=session_id,
                    ordinal=pending_section.ordinal,
                    section=generated_section,
                    lease=lease,
                )

            print(
                "Report section "
                f"{pending_section.ordinal} persisted "
                f"in {perf_counter() - start:.1f}s."
            )

        #
        # All planned sections must now be durable.
        #

        generated_sections = (
            self._get_generated_sections(
                session_id
            )
        )

        if len(generated_sections) != len(plan.sections):

            raise RuntimeError(
                "Report section generation is incomplete."
            )

        completed_sections = []

        for section in generated_sections:

            completed_sections.append(
                ReportSection(
                    heading=section.heading,
                    content=section.content,
                    reviewed_claim_ids=(
                        section.reviewed_claim_ids
                    ),
                )
            )

        #
        # Recover or generate synthesis only after
        # all sections have been persisted.
        #

        with self.session_factory() as db:

            synthesis_repository = (
                ReportSynthesisRepository(
                    db
                )
            )

            synthesis = (
                synthesis_repository.get_for_session(
                    session_id
                )
            )

        if synthesis is None:

            self._check_execution(
                execution_guard
            )

            print()
            print(
                "Generating report synthesis...",
                flush=True,
            )

            start = perf_counter()

            synthesis = (
                self.report_synthesis_agent.generate(
                    topic=topic,
                    plan=plan,
                    sections=completed_sections,
                    reviewed_evidence=reviewed_evidence,
                    scope_definition=scope_definition,
                )
            )

            self._check_execution(
                execution_guard
            )

            with self.session_factory() as db:

                synthesis_repository = (
                    ReportSynthesisRepository(
                        db
                    )
                )

                synthesis_repository.save_synthesis_fenced(
                    session_id=session_id,
                    synthesis=synthesis,
                    lease=lease,
                )

            print(
                "Report synthesis persisted in "
                f"{perf_counter() - start:.1f}s."
            )

        else:

            print()
            print(
                "Recovered persisted report synthesis."
            )

        #
        # Assemble the complete report from durable
        # components and validate its provenance.
        #

        self._check_execution(
            execution_guard
        )

        report = self.report_assembler.assemble(
            plan=plan,
            generated_sections=generated_sections,
            synthesis=synthesis,
            valid_reviewed_claim_ids=(
                valid_reviewed_claim_ids
            ),
        )

        self.validator.validate_claim_references(
            report=report,
            valid_reviewed_claim_ids=(
                valid_reviewed_claim_ids
            ),
        )

        print()
        print(
            "Final report assembly and "
            "provenance validation passed."
        )

        #
        # Persist the final report as one fenced,
        # atomic transaction.
        #

        self._check_execution(
            execution_guard
        )

        with self.session_factory() as db:

            report_repository = (
                ReportRepository(
                    db
                )
            )

            report_id = (
                report_repository.save_report_fenced(
                    session_id=session_id,
                    report=report,
                    lease=lease,
                )
            )

        print(
            "Final research report persisted. "
            f"Report ID: {report_id}"
        )

        return {}
