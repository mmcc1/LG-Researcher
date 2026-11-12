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
