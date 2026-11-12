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

from pydantic import BaseModel, Field


class ReportSection(BaseModel):

    heading: str = Field(
        description=(
            "A concise heading describing the "
            "subject of this report section."
        )
    )

    content: str = Field(
        description=(
            "The evidence-based narrative for this "
            "section of the report. It must be based "
            "only on the supplied reviewed research "
            "material."
        )
    )

    reviewed_claim_ids: list[int] = Field(
        description=(
            "The IDs of reviewed claims that support "
            "the content of this section."
        )
    )


class ResearchReport(BaseModel):

    title: str = Field(
        description=(
            "A concise title for the research report."
        )
    )

    executive_summary: str = Field(
        description=(
            "A concise summary of the principal "
            "conclusions of the research."
        )
    )

    sections: list[ReportSection] = Field(
        description=(
            "The main evidence-based sections of "
            "the research report."
        )
    )

    conclusions: str = Field(
        description=(
            "The overall conclusions that can "
            "reasonably be drawn from the reviewed "
            "evidence."
        )
    )

    limitations: list[str] = Field(
        description=(
            "Important limitations, unresolved "
            "contradictions, evidence gaps, or areas "
            "where the available evidence was "
            "insufficient."
        )
    )


#
# Read models used when reconstructing a persisted
# report from the database.
#


class PersistedReportSection(BaseModel):

    id: int

    ordinal: int

    heading: str

    content: str

    reviewed_claim_ids: list[int]


class PersistedResearchReport(BaseModel):

    id: int

    research_session_id: str

    title: str

    executive_summary: str

    sections: list[
        PersistedReportSection
    ]

    conclusions: str

    limitations: list[str]