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

from domain.report import ResearchReport


class ReportValidator:

    def validate_claim_references(
        self,
        report: ResearchReport,
        valid_reviewed_claim_ids: set[int],
    ) -> None:

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
                "Report contains invalid reviewed "
                "claim references: "
                f"{invalid_text}"
            )