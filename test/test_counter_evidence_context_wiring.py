from domain.search import (
    SearchPlan,
    SearchQuery,
)

from graph.state import (
    ResearchState,
)

from nodes.create_search_plan import (
    CreateSearchPlanNode,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)


SESSION_ID = (
    "fae69e3e-58d2-4c6a-8ac1-85cf6994db06"
)

QUESTION_ID = 100


class FakeSearchPlanner:

    def __init__(
        self,
    ):
        self.topic = None
        self.question = None
        self.purpose = None
        self.instructions = None
        self.existing_evidence_context = None

    def create_plan(
        self,
        topic: str,
        question: str,
        purpose: str = "initial",
        instructions: str | None = None,
        existing_evidence_context:
            str | None = None,
    ) -> SearchPlan:

        self.topic = topic
        self.question = question
        self.purpose = purpose
        self.instructions = instructions

        self.existing_evidence_context = (
            existing_evidence_context
        )

        return SearchPlan(
            queries=[
                SearchQuery(
                    query=(
                        "synthetic counter-evidence "
                        "query"
                    ),
                    rationale=(
                        "Tests evidence-context wiring."
                    ),
                )
            ]
        )


print()
print(
    "COUNTER-EVIDENCE CONTEXT WIRING TEST"
)
print(
    "===================================="
)


#
# Load the genuine session/question.
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        session_repository.get(
            SESSION_ID
        )
    )

    question = (
        session_repository.get_question(
            QUESTION_ID
        )
    )

    if research_session is None:
        raise ValueError(
            "Research session not found."
        )

    if question is None:
        raise ValueError(
            "Research question not found."
        )

    topic = research_session.topic
    question_text = question.question


#
# Create a synthetic attempt solely to exercise
# the CreateSearchPlanNode correlation path.
#

with SessionLocal() as db:

    attempt_repository = (
        SearchAttemptRepository(db)
    )

    attempt = (
        attempt_repository.create(
            session_id=SESSION_ID,
            question_id=QUESTION_ID,
            purpose="counter_evidence",
            instructions=(
                "Test evidence-aware planning."
            ),
        )
    )

    attempt_id = attempt.id


#
# The node requires a running attempt.
#

with SessionLocal() as db:

    attempt_repository = (
        SearchAttemptRepository(db)
    )

    attempt_repository.mark_running(
        attempt_id
    )


print()
print(
    f"Attempt ID: {attempt_id}"
)


fake_planner = FakeSearchPlanner()


node = CreateSearchPlanNode(
    search_planner=fake_planner,
    session_factory=SessionLocal,
)


state: ResearchState = {
    "session_id": SESSION_ID,
    "topic": topic,
    "resume": True,
    "resume_phase": "researching",
    "execution_target": "research",

    "research_plan": None,

    "current_question_id": QUESTION_ID,
    "current_question": question_text,

    "search_required": True,

    "current_search_attempt_id": (
        attempt_id
    ),

    "search_plan": None,
    "search_results": [],

    "current_review_question_id": None,
    "current_review_question": None,
}


result = node(
    state
)


print()
print(
    "CAPTURED PLANNER INPUT"
)
print(
    "----------------------"
)

print(
    f"Purpose: "
    f"{fake_planner.purpose}"
)

print(
    f"Instructions: "
    f"{fake_planner.instructions}"
)

print()
print(
    "EXISTING EVIDENCE CONTEXT"
)
print(
    "-------------------------"
)

print(
    fake_planner.existing_evidence_context
)


assert (
    fake_planner.purpose
    == "counter_evidence"
)

assert (
    fake_planner.instructions
    == "Test evidence-aware planning."
)

assert (
    fake_planner.existing_evidence_context
    is not None
)

assert (
    "Existing research claims:"
    in fake_planner.existing_evidence_context
)

assert (
    len(
        fake_planner.existing_evidence_context
    )
    > 0
)

assert (
    result["search_plan"]
    is not None
)


print()
print(
    "Context length: "
    f"{len(fake_planner.existing_evidence_context)}"
)


print()
print(
    "===================================="
)
print("PASS")
print(
    "===================================="
)