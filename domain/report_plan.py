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


class ProposedReportSection(BaseModel):

    heading: str = Field(
        min_length=1,
        description=(
            "A concise heading for the report section."
        ),
    )

    purpose: str = Field(
        min_length=1,
        description=(
            "The subject, evidence and questions "
            "that this section should address."
        ),
    )

    reviewed_claim_ids: list[int] = Field(
        description=(
            "Reviewed claim IDs allocated to this "
            "section. Use only IDs supplied in the "
            "reviewed research material."
        ),
    )


class ProposedReportPlan(BaseModel):

    title: str = Field(
        min_length=1,
        description=(
            "The proposed title of the research report."
        ),
    )

    sections: list[
        ProposedReportSection
    ] = Field(
        min_length=1,
        description=(
            "The proposed report sections in their "
            "intended presentation order."
        ),
    )


class PlannedReportSection(BaseModel):

    ordinal: int = Field(
        ge=1,
    )

    heading: str

    purpose: str

    target_word_count: int = Field(
        ge=1,
    )

    reviewed_claim_ids: list[int]


class ReportPlan(BaseModel):

    title: str

    target_word_count: int = Field(
        ge=1,
    )

    executive_summary_word_count: int = Field(
        ge=0,
    )

    conclusions_word_count: int = Field(
        ge=0,
    )

    limitations_word_count: int = Field(
        ge=0,
    )

    sections: list[
        PlannedReportSection
    ]
