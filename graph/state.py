from typing import NotRequired, TypedDict

from domain.research_plan import ResearchPlan
from domain.search import SearchPlan, SearchResult


class ResearchState(TypedDict):

    session_id: str

    topic: str

    scope: NotRequired[str | None]

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