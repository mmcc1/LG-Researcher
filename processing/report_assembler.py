
from domain.report import (
    ReportSection,
    ResearchReport,
)

from domain.report_plan import (
    ReportPlan,
)

from domain.report_synthesis import (
    ReportSynthesis,
)

from persistence.report_generated_section_repository import (
    PersistedGeneratedSection,
)

from processing.report_validator import (
    ReportValidator,
)


class ReportAssembler:

    def __init__(
        self,
    ):

        self.validator = ReportValidator()


    def assemble(
        self,
        plan: ReportPlan,
        generated_sections: list[PersistedGeneratedSection],
        synthesis: ReportSynthesis,
        valid_reviewed_claim_ids: set[int],
    ) -> ResearchReport:

        if not plan.sections:

            raise ValueError(
                "Cannot assemble a report without "
                "planned sections."
            )

        if len(generated_sections) != len(plan.sections):

            raise ValueError(
                "Cannot assemble report: generated "
                "section count does not match "
                "the persisted report plan."
            )

        planned_ordinals = [
            section.ordinal
            for section in plan.sections
        ]

        if planned_ordinals != list(
            range(
                1,
                len(plan.sections) + 1,
            )
        ):

            raise ValueError(
                "Report plan section ordinals "
                "must be consecutive."
            )

        generated_by_ordinal = {}

        for generated_section in generated_sections:

            if generated_section.ordinal in generated_by_ordinal:

                raise ValueError(
                    "Duplicate generated report "
                    "section ordinal: "
                    f"{generated_section.ordinal}"
                )

            generated_by_ordinal[
                generated_section.ordinal
            ] = generated_section

        report_sections = []

        for planned_section in plan.sections:

            generated_section = (
                generated_by_ordinal.get(
                    planned_section.ordinal
                )
            )

            if generated_section is None:

                raise ValueError(
                    "Missing generated report section: "
                    f"{planned_section.ordinal}"
                )

            if (
                generated_section.heading
                != planned_section.heading
            ):

                raise ValueError(
                    "Generated report section heading "
                    "does not match the plan for "
                    f"ordinal {planned_section.ordinal}."
                )

            if not generated_section.content.strip():

                raise ValueError(
                    "Generated report section content "
                    "is empty for ordinal "
                    f"{planned_section.ordinal}."
                )

            allocated_claim_ids = set(
                planned_section.reviewed_claim_ids
            )

            generated_claim_ids = (
                generated_section.reviewed_claim_ids
            )

            if len(generated_claim_ids) != len(
                set(generated_claim_ids)
            ):

                raise ValueError(
                    "Duplicate reviewed claim references "
                    "in generated report section "
                    f"{planned_section.ordinal}."
                )

            invalid_allocations = (
                set(generated_claim_ids)
                - allocated_claim_ids
            )

            if invalid_allocations:

                raise ValueError(
                    "Generated report section references "
                    "claims not allocated by the plan: "
                    f"{sorted(invalid_allocations)}"
                )

            report_section = ReportSection(
                heading=generated_section.heading,
                content=generated_section.content,
                reviewed_claim_ids=(
                    list(
                        generated_claim_ids
                    )
                ),
            )

            report_sections.append(
                report_section
            )

        if not synthesis.executive_summary.strip():

            raise ValueError(
                "Cannot assemble report with "
                "an empty executive summary."
            )

        if not synthesis.conclusions.strip():

            raise ValueError(
                "Cannot assemble report with "
                "empty conclusions."
            )

        for limitation in synthesis.limitations:

            if not limitation.strip():

                raise ValueError(
                    "Cannot assemble report with "
                    "an empty limitation."
                )

        report = ResearchReport(
            title=plan.title,
            executive_summary=(
                synthesis.executive_summary
            ),
            sections=report_sections,
            conclusions=synthesis.conclusions,
            limitations=list(
                synthesis.limitations
            ),
        )

        self.validator.validate_claim_references(
            report=report,
            valid_reviewed_claim_ids=(
                valid_reviewed_claim_ids
            ),
        )

        return report
