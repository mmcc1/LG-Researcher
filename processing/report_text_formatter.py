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


from domain.report_citation_registry import (
    ReportCitationRegistryResult,
)


class ReportTextFormatter:

    def format(
        self,
        report,
        citation_registry: ReportCitationRegistryResult,
    ) -> str:

        lines = []


        if (
            report.research_session_id
            != citation_registry.research_session_id
        ):

            raise ValueError(
                "Report and citation registry "
                "belong to different research sessions."
            )

        citations_by_section = {}

        for section_citations in citation_registry.sections:

            if section_citations.section_id in citations_by_section:

                raise ValueError(
                    "Duplicate citation references "
                    "for report section: "
                    f"{section_citations.section_id}"
                )

            citations_by_section[
                section_citations.section_id
            ] = section_citations

        report_section_ids = {
            section.id
            for section in report.sections
        }

        if (
            set(citations_by_section)
            != report_section_ids
        ):

            raise ValueError(
                "Citation registry sections do not "
                "match the persisted report sections."
            )

        bibliography_numbers = [
            entry.number
            for entry in citation_registry.bibliography
        ]

        expected_numbers = list(
            range(
                1,
                len(bibliography_numbers) + 1,
            )
        )

        if bibliography_numbers != expected_numbers:

            raise ValueError(
                "Bibliography numbering is invalid."
            )

        valid_numbers = set(
            bibliography_numbers
        )

        for section_citations in citation_registry.sections:

            referenced_numbers = (
                section_citations.supporting_numbers
                + section_citations.contradicting_numbers
            )

            if not set(referenced_numbers).issubset(
                valid_numbers
            ):

                raise ValueError(
                    "Section contains an unknown "
                    "bibliography reference."
                )


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

            
            section_citations = (
                citations_by_section[
                    section.id
                ]
            )

            supporting_references = [
                f"[{number}]"
                for number in (
                    section_citations.supporting_numbers
                )
            ]

            contradicting_references = [
                f"[{number}]"
                for number in (
                    section_citations.contradicting_numbers
                )
            ]

            if supporting_references:

                lines.append(
                    "Sources cited: "
                    + ", ".join(
                        supporting_references
                    )
                )

            else:

                lines.append(
                    "Sources cited: None"
                )

            if contradicting_references:

                lines.append(
                    "Contradicting evidence: "
                    + ", ".join(
                        contradicting_references
                    )
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

        lines.append(
            "-" * 70
        )

        lines.append(
            "BIBLIOGRAPHY"
        )

        lines.append(
            "-" * 70
        )

        lines.append("")

        for entry in citation_registry.bibliography:

            lines.append(
                f"[{entry.number}] {entry.title}"
            )

            lines.append(
                entry.url
            )

            lines.append("")

        return "\n".join(
            lines
        )
