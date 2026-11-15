
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

from pydantic import (
    BaseModel,
    Field,
)


class BibliographyEntry(BaseModel):

    number: int

    title: str

    url: str

    source_ids: list[int] = Field(
        default_factory=list
    )


class SectionCitationReferences(BaseModel):

    section_id: int

    ordinal: int

    supporting_numbers: list[int] = Field(
        default_factory=list
    )

    contradicting_numbers: list[int] = Field(
        default_factory=list
    )


class ReportCitationRegistryResult(BaseModel):

    research_session_id: str

    sections: list[
        SectionCitationReferences
    ] = Field(
        default_factory=list
    )

    bibliography: list[
        BibliographyEntry
    ] = Field(
        default_factory=list
    )
