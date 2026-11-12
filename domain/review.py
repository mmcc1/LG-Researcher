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


class ReviewedClaim(BaseModel):

    claim: str = Field(
        description=(
            "A conclusion supported by one or more "
            "of the supplied research findings."
        )
    )

    supporting_finding_ids: list[int] = Field(
        description=(
            "The IDs of findings that support "
            "this conclusion."
        )
    )

    contradicting_finding_ids: list[int] = Field(
        description=(
            "The IDs of findings that contradict "
            "or materially challenge this conclusion."
        )
    )

    confidence: Literal[
        "low",
        "medium",
        "high",
    ] = Field(
        description=(
            "Confidence in the conclusion based "
            "only on the supplied evidence."
        )
    )


class ResearchQuestionReview(BaseModel):

    answer: str = Field(
        description=(
            "A concise evidence-based answer to "
            "the research question. Focus only on "
            "answering the question. Do not discuss "
            "confidence, contradictions, evidence "
            "gaps, or sufficiency here because those "
            "are represented separately."
        )
    )

    reviewed_claims: list[ReviewedClaim] = Field(
        description=(
            "The important conclusions supported "
            "by the supplied findings."
        )
    )

    contradictions: list[str] = Field(
        description=(
            "Important disagreements or tensions "
            "within the supplied evidence."
        )
    )

    evidence_gaps: list[str] = Field(
        description=(
            "Important aspects of the research "
            "question that the supplied evidence "
            "does not adequately answer."
        )
    )

    overall_confidence: Literal[
        "low",
        "medium",
        "high",
    ]

    sufficient_evidence: bool = Field(
        description=(
            "Whether the supplied evidence is "
            "sufficient to answer the research "
            "question reasonably well."
        )
    )


class PersistedReviewedClaim(BaseModel):

    id: int

    claim: str

    confidence: Literal[
        "low",
        "medium",
        "high",
    ]

    supporting_finding_ids: list[int]

    contradicting_finding_ids: list[int]


class PersistedQuestionReview(BaseModel):

    id: int

    research_question_id: int

    category: str

    question: str

    answer: str

    overall_confidence: Literal[
        "low",
        "medium",
        "high",
    ]

    sufficient_evidence: bool

    reviewed_claims: list[
        PersistedReviewedClaim
    ]

    contradictions: list[str]

    evidence_gaps: list[str]