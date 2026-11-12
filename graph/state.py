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

from typing import NotRequired, TypedDict

from domain.research_plan import ResearchPlan
from domain.search import SearchPlan, SearchResult


class ResearchState(TypedDict):

    session_id: str

    topic: str

    scope: NotRequired[str | None]
    
    user_questions: NotRequired[list[str]]

    resume: bool

    resume_phase: str | None

    #
    # Controls how far this graph invocation
    # is authorised to proceed.
    #
    # "complete"
    #     Continue through research, review,
    #     and reporting.
    #
    # "research"
    #     Stop after the research phase has
    #     durably completed.
    #

    execution_target: str

        #
    # Cooperative pause state.
    #
    # This is a snapshot of the durable
    # ResearchSession.pause_requested flag.
    #
    # It does not itself mean that execution
    # has stopped. A pause boundary reads this
    # value and decides whether the graph may
    # continue.
    #

    pause_requested: NotRequired[bool]

    research_plan: ResearchPlan | None

    #
    # Research phase state.
    #

    current_question_id: int | None

    current_question: str | None

    search_required: bool

    current_search_attempt_id: int | None

    search_plan: SearchPlan | None

    search_results: list[SearchResult]

    #
    # Review phase state.
    #

    current_review_question_id: int | None

    current_review_question: str | None