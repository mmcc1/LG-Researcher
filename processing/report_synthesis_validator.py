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

from domain.report_plan import ReportPlan

from domain.report_synthesis import ReportSynthesis

from processing.report_section_validator import (
    ReportSectionValidator,
)


@dataclass(frozen=True)
class SynthesisValidationResult:

    executive_summary_word_count: int

    conclusions_word_count: int

    limitations_word_count: int

    total_word_count: int


class ReportSynthesisValidator:

    def __init__(
        self,
    ):

        self.section_validator = (
            ReportSectionValidator()
        )


    def validate(
        self,
        synthesis: ReportSynthesis,
        plan: ReportPlan,
    ) -> SynthesisValidationResult:

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

        executive_summary_word_count = (
            self.section_validator.count_words(
                synthesis.executive_summary
            )
        )

        conclusions_word_count = (
            self.section_validator.count_words(
                synthesis.conclusions
            )
        )

        limitations_word_count = sum(
            self.section_validator.count_words(
                limitation
            )
            for limitation in synthesis.limitations
        )

        total_word_count = (
            executive_summary_word_count
            + conclusions_word_count
            + limitations_word_count
        )

        return SynthesisValidationResult(
            executive_summary_word_count=(
                executive_summary_word_count
            ),
            conclusions_word_count=(
                conclusions_word_count
            ),
            limitations_word_count=(
                limitations_word_count
            ),
            total_word_count=(
                total_word_count
            ),
        )
