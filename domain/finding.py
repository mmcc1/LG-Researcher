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