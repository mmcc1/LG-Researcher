from config import settings

from agents.search_planner import (
    SearchPlanner,
)

from models.factory import (
    ChatModelFactory,
)


print()
print(
    "REAL COUNTER-EVIDENCE SEARCH PLANNER TEST"
)
print(
    "========================================="
)


#
# Use the researcher model because SearchPlanner
# currently uses AgentModels.researcher in the
# production graph.
#

model = ChatModelFactory.create(
    settings.researcher_model
)

search_planner = SearchPlanner(
    model=model
)


topic = (
    "Bitcoin proof-of-work hashing"
)

question = (
    "What role does SHA-256 play "
    "in Bitcoin proof-of-work?"
)

instructions = (
    "Look specifically for credible "
    "technical evidence that challenges, "
    "qualifies, or limits common claims "
    "about the security role of SHA-256 "
    "in Bitcoin proof-of-work."
)


print()
print("Calling Qwen...")
print()


plan = search_planner.create_plan(
    topic=topic,
    question=question,
    purpose="counter_evidence",
    instructions=instructions,
)


print("SEARCH PLAN")
print("-----------")


assert plan is not None

assert len(plan.queries) > 0

assert len(plan.queries) <= 3


for index, query in enumerate(
    plan.queries,
    start=1,
):

    assert query.query.strip()
    assert query.rationale.strip()

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


print()
print(
    "========================================="
)
print("PASS")
print(
    "========================================="
)
print(
    "Qwen produced a valid "
    "counter-evidence SearchPlan."
)