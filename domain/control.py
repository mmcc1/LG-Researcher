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

from pydantic import (
    BaseModel,
    Field,
)


ControlOperation = Literal[
    "status",
    "start_research",
    "add_question",
    "modify_scope",
    "deeper_research",
    "counter_evidence",
    "generate_report",
    "pause",
    "resume",
    "help",
]


class ControlContext(BaseModel):

    session_id: str | None = Field(
        default=None,
        description=(
            "The active research session ID, "
            "if one exists."
        ),
    )

    topic: str | None = Field(
        default=None,
        description=(
            "The topic of the active research "
            "session, if one exists."
        ),
    )

    scope: str | None = Field(
        default=None,
        description=(
            "The current durable research scope "
            "of the active session, if one exists."
        ),
    )

    status: str | None = Field(
        default=None,
        description=(
            "The persisted lifecycle status of "
            "the active research session."
        ),
    )

    pause_requested: bool = Field(
        default=False,
        description=(
            "Whether cooperative suspension has "
            "been requested for the active "
            "research session."
        ),
    )


class ControlCommand(BaseModel):

    operation: ControlOperation = Field(
        description=(
            "The research-system operation "
            "requested by the user."
        )
    )

    topic: str | None = Field(
        default=None,
        description=(
            "The research topic when the "
            "operation requires one."
        ),
    )

    question: str | None = Field(
        default=None,
        description=(
            "A specific research question "
            "when the operation targets or "
            "adds a question."
        ),
    )

    scope: str | None = Field(
        default=None,
        description=(
            "The persistent research scope. "
            "For start_research, this is the "
            "initial durable research scope. "
            "For modify_scope, this is the "
            "complete replacement research scope."
        ),
    )

    instructions: str | None = Field(
        default=None,
        description=(
            "Additional user instructions "
            "or requested changes relevant "
            "to the operation."
        ),
    )


class ResearchStatus(BaseModel):

    session_id: str
    topic: str
    status: str

    pause_requested: bool

    total_questions: int
    pending_questions: int
    researching_questions: int
    researched_questions: int
    reviewing_questions: int
    reviewed_questions: int

    report_available: bool


class ControlHelp(BaseModel):

    available_operations: list[str]


class ResearchExecutionResult(BaseModel):

    session_id: str

    topic: str

    status: str

    pause_requested: bool = False


class ReportResult(BaseModel):
    report_id: int
    session_id: str
    title: str
    executive_summary: str
    conclusions: str
    limitations: list[str]


class AddQuestionResult(BaseModel):
    question_id: int
    session_id: str
    question: str
    status: str


class ModifyScopeResult(BaseModel):
    session_id: str
    topic: str
    scope: str
    status: str


class PauseResult(BaseModel):
    session_id: str
    topic: str
    status: str
    pause_requested: bool


class DeeperResearchResult(BaseModel):
    search_attempt_id: int
    session_id: str
    question_id: int
    question: str
    instructions: str | None
    status: str


class CounterEvidenceResult(BaseModel):
    search_attempt_id: int
    session_id: str
    question_id: int
    question: str
    instructions: str | None
    status: str


class ControlResult(BaseModel):

    operation: ControlOperation

    success: bool

    message: str

    status: ResearchStatus | None = None

    help: ControlHelp | None = None

    research: ResearchExecutionResult | None = None

    report: ReportResult | None = None

    question: AddQuestionResult | None = None

    deeper_research: DeeperResearchResult | None = None

    counter_evidence: CounterEvidenceResult | None = None

    scope: ModifyScopeResult | None = None

    pause: PauseResult | None = None


