from domain.research_plan import (
    ResearchPlan,
    ResearchQuestionPlan,
)

from domain.search import (
    SearchPlan,
    SearchQuery,
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


print()
print("SEARCH PLAN SCOPE TEST")
print("======================")


#
# -------------------------------------------------
# Fake SearchPlanner.
#
# Records exactly what CreateSearchPlanNode passes
# across the agent boundary.
#
# No Qwen call is made.
# -------------------------------------------------
#

class FakeSearchPlanner:

    def __init__(self):
        self.call = None

    def create_plan(
        self,
        topic: str,
        question: str,
        scope: str | None = None,
        purpose: str = "initial",
        instructions: str | None = None,
        existing_evidence_context: str | None = None,
    ) -> SearchPlan:

        self.call = {
            "topic": topic,
            "question": question,
            "scope": scope,
            "purpose": purpose,
            "instructions": instructions,
            "existing_evidence_context": (
                existing_evidence_context
            ),
        }

        return SearchPlan(
            queries=[
                SearchQuery(
                    query="test query",
                    rationale=(
                        "Test query returned by "
                        "FakeSearchPlanner."
                    ),
                )
            ]
        )


#
# -------------------------------------------------
# Test research definition.
# -------------------------------------------------
#

topic = (
    "The effect of Bitcoin mining "
    "on energy systems"
)

scope = (
    "Focus on electricity pricing, "
    "grid incentives, and "
    "renewable-energy investment."
)

question_text = (
    "How does Bitcoin mining affect "
    "electricity markets?"
)


#
# -------------------------------------------------
# Create test session and persisted question.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic=topic
        )
    )

    session_id = research_session.id

    repository.set_scope(
        session_id=session_id,
        scope=scope,
    )

    plan = ResearchPlan(
        topic=topic,
        questions=[
            ResearchQuestionPlan(
                category="Energy economics",
                question=question_text,
                rationale=(
                    "This question examines the "
                    "relationship between Bitcoin "
                    "mining and electricity markets."
                ),
            )
        ],
    )

    repository.save_plan(
        session_id=session_id,
        plan=plan,
    )

    questions = (
        repository.get_questions(
            session_id
        )
    )

    assert len(questions) == 1

    question = questions[0]

    question_id = question.id


print()
print(
    f"Test session: {session_id}"
)

print(
    f"Question ID: {question_id}"
)


#
# -------------------------------------------------
# Create search attempt.
#
# SearchAttemptRepository.create() creates the
# attempt in "pending" state.
#
# The production lifecycle then explicitly moves
# the attempt to "running" before search planning.
# -------------------------------------------------
#

with SessionLocal() as db:

    attempt_repository = (
        SearchAttemptRepository(db)
    )

    attempt = (
        attempt_repository.create(
            session_id=session_id,
            question_id=question_id,
            purpose="initial",
            instructions=None,
        )
    )

    attempt_id = attempt.id

    assert attempt.status == "pending"

    print(
        f"Search attempt: {attempt_id}"
    )

    print(
        f"Initial attempt status: "
        f"{attempt.status}"
    )

    #
    # Reproduce the real production lifecycle.
    #

    attempt_repository.mark_running(
        attempt_id=attempt_id,
    )

    attempt = (
        attempt_repository.get(
            attempt_id
        )
    )

    assert attempt is not None

    attempt_status = attempt.status


print(
    f"Planning attempt status: "
    f"{attempt_status}"
)


assert attempt_status == "running"


#
# -------------------------------------------------
# CreateSearchPlanNode requires the active attempt
# to be running.
#
# The production SearchAttemptRepository is
# responsible for establishing that lifecycle
# state when the attempt is created.
# -------------------------------------------------
#

assert attempt_status == "running", (
    "Expected SearchAttemptRepository.create() "
    "to create a running attempt, but received "
    f"status '{attempt_status}'."
)


#
# -------------------------------------------------
# Deliberately give graph state a stale topic.
#
# This is important:
#
# CreateSearchPlanNode must load the authoritative
# topic and scope from SQL rather than trusting the
# stale graph-state topic.
# -------------------------------------------------
#

state = {
    "session_id": session_id,

    "topic": (
        "THIS STALE TOPIC MUST NOT BE USED"
    ),

    "current_question_id": question_id,

    "current_question": question_text,

    "current_search_attempt_id": attempt_id,
}


#
# -------------------------------------------------
# Execute node using fake planner.
# -------------------------------------------------
#

fake_planner = FakeSearchPlanner()


node = CreateSearchPlanNode(
    search_planner=fake_planner,
    session_factory=SessionLocal,
)


print()
print("EXECUTING NODE")
print("--------------")


result = node(state)


#
# -------------------------------------------------
# Verify the SearchPlanner boundary.
# -------------------------------------------------
#

assert fake_planner.call is not None


print()
print(
    "VALUES RECEIVED BY SEARCH PLANNER"
)
print(
    "---------------------------------"
)

print(
    f"Topic:    "
    f"{fake_planner.call['topic']}"
)

print(
    f"Question: "
    f"{fake_planner.call['question']}"
)

print(
    f"Scope:    "
    f"{fake_planner.call['scope']}"
)

print(
    f"Purpose:  "
    f"{fake_planner.call['purpose']}"
)


#
# Authoritative topic must come from SQL.
#

assert (
    fake_planner.call["topic"]
    == topic
)


#
# The current persisted question must reach the
# planner unchanged.
#

assert (
    fake_planner.call["question"]
    == question_text
)


#
# The new persistent scope must reach the planner
# unchanged.
#

assert (
    fake_planner.call["scope"]
    == scope
)


#
# Search-attempt semantics must also remain intact.
#

assert (
    fake_planner.call["purpose"]
    == "initial"
)

assert (
    fake_planner.call[
        "instructions"
    ]
    is None
)

assert (
    fake_planner.call[
        "existing_evidence_context"
    ]
    is None
)


#
# Verify the node still returns its normal
# search_plan graph-state update.
#

assert "search_plan" in result

assert result["search_plan"] is not None

assert len(
    result["search_plan"].queries
) == 1

assert (
    result[
        "search_plan"
    ].queries[0].query
    == "test query"
)


print()
print(
    "Persisted topic used: PASSED"
)

print(
    "Persisted scope passed to "
    "SearchPlanner: PASSED"
)

print(
    "Stale graph-state topic ignored: PASSED"
)

print(
    "Search-attempt semantics preserved: PASSED"
)

print(
    "SearchPlan return contract preserved: PASSED"
)


print()
print("======================")
print("PASS")
print("======================")

print(
    "CreateSearchPlanNode correctly "
    "uses durable research scope."
)