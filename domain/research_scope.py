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

from pydantic import (
    BaseModel,
    Field,
)


class ResearchTermDefinition(BaseModel):

    term: str = Field(
        description=(
            "A term whose meaning is important "
            "to understanding the research subject."
        )
    )

    definition: str = Field(
        description=(
            "The intended meaning of the term "
            "within this research."
        )
    )


class ResearchRelatedConcept(BaseModel):

    concept: str = Field(
        description=(
            "A concept related to, but not "
            "necessarily equivalent to, "
            "the primary research subject."
        )
    )

    relationship: str = Field(
        description=(
            "How the concept relates to "
            "the primary research subject."
        )
    )

    distinction: str = Field(
        description=(
            "The important differences that "
            "must be preserved when interpreting "
            "evidence about this concept."
        )
    )


class ResearchScopeDefinition(BaseModel):

    primary_subject: str = Field(
        description=(
            "A precise description of the "
            "primary subject being investigated."
        )
    )

    research_objective: str = Field(
        description=(
            "What the research aims to establish."
        )
    )

    definitions: list[ResearchTermDefinition] = Field(
        default_factory=list,
        description=(
            "Definitions of important terminology."
        ),
    )

    included_concepts: list[str] = Field(
        default_factory=list,
        description=(
            "Concepts directly within the "
            "defined research scope."
        ),
    )

    related_concepts: list[ResearchRelatedConcept] = Field(
        default_factory=list,
        description=(
            "Related concepts that may provide "
            "useful context but must not be "
            "treated as equivalent without evidence."
        ),
    )

    excluded_concepts: list[str] = Field(
        default_factory=list,
        description=(
            "Concepts outside the research scope "
            "unless a direct relationship is "
            "established by evidence."
        ),
    )

    ambiguities: list[str] = Field(
        default_factory=list,
        description=(
            "Ambiguous terminology, competing "
            "interpretations, or unresolved "
            "conceptual distinctions."
        ),
    )

    evidence_requirements: list[str] = Field(
        default_factory=list,
        description=(
            "Requirements for evaluating evidence "
            "and avoiding unsupported equivalence "
            "between related concepts."
        ),
    )