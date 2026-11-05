from agents.search_planner import (
    SearchPlanner,
)

from config import settings

from models.factory import (
    ChatModelFactory,
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


SESSION_ID = (
    "fae69e3e-58d2-4c6a-8ac1-85cf6994db06"
)

QUESTION_ID = 100

ATTEMPT_ID = 16


print()
print(
    "REAL EVIDENCE-AWARE COUNTER-EVIDENCE "
    "PLANNER TEST"
)
print(
    "======================================"
)


#
# Load authoritative session/question data.
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.get(
            SESSION_ID
        )
    )

    question = (
        repository.get_question(
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
# Use the real configured researcher model.
#

model = ChatModelFactory.create(
    settings.researcher_model
)

search_planner = SearchPlanner(
    model=model
)


node = CreateSearchPlanNode(
    search_planner=search_planner,
    session_factory=SessionLocal,
)


state = {
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
        ATTEMPT_ID
    ),

    "search_plan": None,
    "search_results": [],

    "current_review_question_id": None,
    "current_review_question": None,
}


print()
print(
    f"Session ID: {SESSION_ID}"
)

print(
    f"Question ID: {QUESTION_ID}"
)

print(
    f"Attempt ID: {ATTEMPT_ID}"
)

print()
print(
    "Invoking real Qwen SearchPlanner..."
)
print()


result = node(
    state
)


plan = result[
    "search_plan"
]


print()
print(
    "EVIDENCE-AWARE SEARCH PLAN"
)
print(
    "--------------------------"
)


for index, query in enumerate(
    plan.queries,
    start=1,
):

    print()
    print(
        f"Query {index}: "
        f"{query.query}"
    )

    print(
        f"Rationale: "
        f"{query.rationale}"
    )


assert plan is not None

assert len(
    plan.queries
) > 0

assert len(
    plan.queries
) <= 3


print()
print(
    "======================================"
)
print("PASS")
print(
    "======================================"
)