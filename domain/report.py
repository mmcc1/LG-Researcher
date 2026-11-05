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