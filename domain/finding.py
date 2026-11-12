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

from typing import Literal

from pydantic import BaseModel, Field


class ExtractedFinding(BaseModel):

    claim: str = Field(
        description=(
            "A concise factual claim supported by "
            "the source document."
        )
    )

    evidence: str = Field(
        description=(
            "A concise paraphrase of the evidence "
            "in the source supporting the claim."
        )
    )

    relevance: str = Field(
        description=(
            "Why this finding is relevant to the "
            "research question."
        )
    )

    confidence: Literal[
        "low",
        "medium",
        "high",
    ] = Field(
        description=(
            "Confidence that the source clearly "
            "supports this finding."
        )
    )


class SourceAnalysis(BaseModel):

    summary: str = Field(
        description=(
            "A concise summary of the parts of the "
            "source relevant to the research question."
        )
    )

    findings: list[ExtractedFinding] = Field(
        description=(
            "Factual findings from the source that "
            "help answer the research question."
        )
    )