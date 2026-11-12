from agents.search_planner import (
    SearchPlanner,
)

from config import settings

from models.factory import (
    ChatModelFactory,
)


TOPIC = (
    "Synthetic deeper research test"
)

QUESTION = (
    "What role does SHA-256 play "
    "in Bitcoin proof-of-work?"
)

INSTRUCTIONS = (
    "Focus specifically on how "
    "double SHA-256 is used during "
    "block-header validation."
)


print()
print(
    "REAL DEEPER RESEARCH "
    "SEARCH PLANNER TEST"
)
print(
    "=============================="
)


#
# Use the same model configuration assigned
# to the researcher role by the application.
#

model = ChatModelFactory.create(
    settings.researcher_model
)


planner = SearchPlanner(
    model=model
)


print()
print(
    "Calling Qwen..."
)
print()


plan = planner.create_plan(
    topic=TOPIC,
    question=QUESTION,
    purpose="deeper_research",
    instructions=INSTRUCTIONS,
)


print(
    "SEARCH PLAN"
)
print(
    "-----------"
)


for index, query in enumerate(
    plan.queries,
    start=1,
):

    print()
    print(
        f"Query {index}:"
    )

    print(
        query.query
    )

    print(
        "Rationale:"
    )

    print(
        query.rationale
    )


#
# Basic structural assertions.
#

assert len(plan.queries) > 0

assert len(plan.queries) <= 3

for query in plan.queries:

    assert query.query.strip()

    assert query.rationale.strip()


print()
print(
    "=============================="
)
print(
    "PASS"
)
print(
    "=============================="
)
print(
    "Qwen produced a valid "
    "deeper-research SearchPlan."
)