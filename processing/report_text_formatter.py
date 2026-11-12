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

class ReportTextFormatter:

    def format(
        self,
        report,
    ) -> str:

        lines = []

        lines.append(
            "=" * 70
        )

        lines.append(
            report.title
        )

        lines.append(
            "=" * 70
        )

        lines.append("")

        lines.append(
            "EXECUTIVE SUMMARY"
        )

        lines.append("")

        lines.append(
            report.executive_summary
        )

        for section in report.sections:

            lines.append("")

            lines.append(
                "-" * 70
            )

            lines.append(
                section.heading
            )

            lines.append(
                "-" * 70
            )

            lines.append("")

            lines.append(
                section.content
            )

            lines.append("")

            claim_ids = [
                str(claim_id)
                for claim_id in section.reviewed_claim_ids
            ]

            lines.append(
                "Reviewed claim IDs: "
                + ", ".join(claim_ids)
            )

        lines.append("")

        lines.append(
            "-" * 70
        )

        lines.append(
            "CONCLUSIONS"
        )

        lines.append(
            "-" * 70
        )

        lines.append("")

        lines.append(
            report.conclusions
        )

        lines.append("")

        lines.append(
            "-" * 70
        )

        lines.append(
            "LIMITATIONS"
        )

        lines.append(
            "-" * 70
        )

        for limitation in report.limitations:

            lines.append(
                f"- {limitation}"
            )

        lines.append("")

        return "\n".join(
            lines
        )