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

class ReviewContextBuilder:

    def build(
        self,
        findings,
        sources_by_id,
    ) -> str:

        parts = []

        for finding in findings:

            source = sources_by_id.get(
                finding.source_id
            )

            if source is None:

                source_title = "Unknown source"
                source_url = "Unknown"

            else:

                source_title = source.title
                source_url = source.final_url

            part = (
                f"FINDING ID: {finding.id}\n"
                f"SOURCE ID: {finding.source_id}\n"
                f"SOURCE TITLE: {source_title}\n"
                f"SOURCE URL: {source_url}\n"
                f"CLAIM:\n{finding.claim}\n\n"
                f"EVIDENCE:\n{finding.evidence}\n\n"
                f"RELEVANCE:\n{finding.relevance}\n\n"
                f"EXTRACTION CONFIDENCE: "
                f"{finding.confidence}"
            )

            parts.append(part)

        return (
            "\n\n"
            "================================\n\n"
        ).join(parts)