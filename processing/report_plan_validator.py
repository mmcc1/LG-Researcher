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

from domain.report_plan import (
    ProposedReportPlan,
    PlannedReportSection,
    ReportPlan,
)


class ReportPlanValidator:

    def validate_claim_references(
        self,
        plan: ProposedReportPlan,
        valid_reviewed_claim_ids: set[int],
    ) -> None:

        invalid_ids = set()

        for section in plan.sections:

            for claim_id in section.reviewed_claim_ids:

                if claim_id not in valid_reviewed_claim_ids:

                    invalid_ids.add(
                        claim_id
                    )

        if invalid_ids:

            invalid_text = ", ".join(
                str(claim_id)
                for claim_id in sorted(
                    invalid_ids
                )
            )

            raise ValueError(
                "Report plan contains invalid reviewed "
                "claim references: "
                f"{invalid_text}"
            )


    def allocate_word_counts(
        self,
        proposed_plan: ProposedReportPlan,
        target_word_count: int,
    ) -> ReportPlan:

        if target_word_count <= 0:

            raise ValueError(
                "Report target word count must be positive."
            )

        section_count = len(
            proposed_plan.sections
        )

        if section_count == 0:

            raise ValueError(
                "Report plan contains no sections."
            )

        executive_summary_words = round(
            target_word_count * 0.05
        )

        conclusions_words = round(
            target_word_count * 0.05
        )

        limitations_words = round(
            target_word_count * 0.03
        )

        reserved_words = (
            executive_summary_words
            + conclusions_words
            + limitations_words
        )

        section_words = (
            target_word_count
            - reserved_words
        )

        if section_words < section_count:

            raise ValueError(
                "Report target is too small to allocate "
                "at least one word to every section."
            )

        base_words = (
            section_words // section_count
        )

        remainder = (
            section_words % section_count
        )

        planned_sections = []

        for index, section in enumerate(
            proposed_plan.sections
        ):

            target_words = base_words

            if index < remainder:

                target_words += 1

            claim_ids = list(
                dict.fromkeys(
                    section.reviewed_claim_ids
                )
            )

            planned_section = (
                PlannedReportSection(
                    ordinal=index + 1,
                    heading=section.heading,
                    purpose=section.purpose,
                    target_word_count=target_words,
                    reviewed_claim_ids=claim_ids,
                )
            )

            planned_sections.append(
                planned_section
            )

        report_plan = ReportPlan(
            title=proposed_plan.title,
            target_word_count=target_word_count,
            executive_summary_word_count=(
                executive_summary_words
            ),
            conclusions_word_count=(
                conclusions_words
            ),
            limitations_word_count=(
                limitations_words
            ),
            sections=planned_sections,
        )

        allocated_words = (
            report_plan.executive_summary_word_count
            + report_plan.conclusions_word_count
            + report_plan.limitations_word_count
        )

        for section in report_plan.sections:

            allocated_words += (
                section.target_word_count
            )

        if allocated_words != target_word_count:

            raise RuntimeError(
                "Report word allocation does not "
                "match the configured target."
            )

        return report_plan
