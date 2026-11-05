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

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)


SESSION_ID = (
    "8325d0ed-407a-43e9-8ba2-be861de668aa"
)

QUESTION_ID = 97

ATTEMPT_ID = 5

QUESTION = (
    "What role does SHA-256 play "
    "in Bitcoin proof-of-work?"
)

EXPECTED_INSTRUCTIONS = (
    "Focus specifically on how "
    "double SHA-256 is used during "
    "block-header validation."
)


class FakeSearchPlanner:

    def __init__(
        self,
    ):
        self.received_topic = None
        self.received_question = None
        self.received_purpose = None
        self.received_instructions = None

    def create_plan(
        self,
        topic: str,
        question: str,
        purpose: str = "initial",
        instructions: str | None = None,
    ) -> SearchPlan:

        self.received_topic = topic
        self.received_question = question
        self.received_purpose = purpose
        self.received_instructions = (
            instructions
        )

        return SearchPlan(
            queries=[
                SearchQuery(
                    query=(
                        "Bitcoin double SHA-256 "
                        "block header validation"
                    ),
                    rationale=(
                        "Test query used to verify that "
                        "deeper-research purpose and "
                        "instructions reach the search "
                        "planner."
                    ),
                )
            ]
        )


print()
print(
    "DEEPER RESEARCH SEARCH PLAN TEST"
)
print(
    "================================"
)


#
# The handler deliberately created attempt 5 as
# pending. In the real graph,
# CheckExistingSearchNode marks it running before
# CreateSearchPlanNode executes.
#
# Reproduce that transition here.
#

with SessionLocal() as db:

    repository = (
        SearchAttemptRepository(db)
    )

    attempt = repository.get(
        ATTEMPT_ID
    )

    assert attempt is not None

    if attempt.status == "pending":

        repository.mark_running(
            ATTEMPT_ID
        )

    else:

        assert (
            attempt.status
            == "running"
        )


planner = FakeSearchPlanner()


node = CreateSearchPlanNode(
    search_planner=planner,
    session_factory=SessionLocal,
)


state = {
    "session_id": SESSION_ID,
    "topic": (
        "Synthetic deeper research test"
    ),
    "current_question_id": QUESTION_ID,
    "current_question": QUESTION,
    "current_search_attempt_id": ATTEMPT_ID,
}


result = node(
    state
)


assert (
    planner.received_purpose
    == "deeper_research"
)

assert (
    planner.received_instructions
    == EXPECTED_INSTRUCTIONS
)

assert (
    planner.received_question
    == QUESTION
)

assert (
    "search_plan"
    in result
)


print()
print(
    "Purpose received:"
)

print(
    planner.received_purpose
)

print()
print(
    "Instructions received:"
)

print(
    planner.received_instructions
)

print()
print(
    "Generated test query:"
)

print(
    result[
        "search_plan"
    ].queries[0].query
)


print()
print(
    "================================"
)
print(
    "PASS"
)
print(
    "================================"
)
print(
    "SearchAttempt purpose and "
    "instructions reached the "
    "SearchPlanner."
)