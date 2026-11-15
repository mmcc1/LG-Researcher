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

import re

from dataclasses import dataclass

from domain.report import (
    ReportSection,
)

from domain.report_plan import (
    PlannedReportSection,
)


@dataclass
class SectionValidationResult:

    actual_word_count: int

    target_word_count: int

    word_count_difference: int

    word_count_ratio: float

    referenced_claim_count: int


class ReportSectionValidator:

    def count_words(
        self,
        content: str,
    ) -> int:

        words = re.findall(
            r"\b[\w]+(?:['’-][\w]+)*\b",
            content,
        )

        return len(
            words
        )

    def validate(
        self,
        section: ReportSection,
        planned_section: PlannedReportSection,
    ) -> SectionValidationResult:

        if section.heading.strip() != (
            planned_section.heading.strip()
        ):

            raise ValueError(
                "Generated section heading does not "
                "match the planned heading."
            )

        if not section.content.strip():

            raise ValueError(
                "Generated report section is empty."
            )

        permitted_claim_ids = set(
            planned_section.reviewed_claim_ids
        )

        referenced_claim_ids = set(
            section.reviewed_claim_ids
        )

        invalid_claim_ids = (
            referenced_claim_ids
            - permitted_claim_ids
        )

        if invalid_claim_ids:

            invalid_text = ", ".join(
                str(claim_id)
                for claim_id in sorted(
                    invalid_claim_ids
                )
            )

            raise ValueError(
                "Generated section contains invalid "
                "reviewed claim references: "
                f"{invalid_text}"
            )

        if len(section.reviewed_claim_ids) != len(
            referenced_claim_ids
        ):

            raise ValueError(
                "Generated section contains duplicate "
                "reviewed claim references."
            )

        actual_word_count = self.count_words(
            section.content
        )

        target_word_count = (
            planned_section.target_word_count
        )

        difference = (
            actual_word_count
            - target_word_count
        )

        ratio = (
            actual_word_count
            / target_word_count
        )

        return SectionValidationResult(
            actual_word_count=actual_word_count,
            target_word_count=target_word_count,
            word_count_difference=difference,
            word_count_ratio=ratio,
            referenced_claim_count=len(
                referenced_claim_ids
            ),
        )
