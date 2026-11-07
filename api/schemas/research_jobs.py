
from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class CreateResearchJobRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
    )

    topic: str = Field(
        min_length=1,
        max_length=1000,
    )

    scope: str | None = None


class AddResearchQuestionRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
    )

    question: str = Field(
        min_length=1,
        max_length=2000,
    )


class ResearchQuestionResponse(BaseModel):

    id: int

    question: str

    created_at: datetime


class ResearchJobResponse(BaseModel):

    id: str

    topic: str

    scope: str | None

    status: str

    research_session_id: str | None

    created_at: datetime

    submitted_at: datetime | None

    started_at: datetime | None

    completed_at: datetime | None

    questions: list[ResearchQuestionResponse]


class ResearchJobActionResponse(BaseModel):

    id: str

    status: str


class AddResearchQuestionResponse(BaseModel):

    id: int

    research_job_id: str

    question: str



class UpdateResearchJobRequest(BaseModel):

    model_config = ConfigDict(
        extra="forbid",
    )

    topic: str = Field(
        min_length=1,
        max_length=1000,
    )

    scope: str | None = None


class ResearchJobListItemResponse(BaseModel):

    id: str

    topic: str

    scope: str | None

    status: str

    research_session_id: str | None

    created_at: datetime

    submitted_at: datetime | None

    started_at: datetime | None

    completed_at: datetime | None


class ResearchJobListResponse(BaseModel):

    items: list[ResearchJobListItemResponse]

    total: int

    limit: int

    offset: int
