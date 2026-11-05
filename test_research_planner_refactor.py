from domain.research_plan import (
    ResearchPlan,
    ResearchQuestionPlan,
)

from agents.research_planner import (
    ResearchPlanner,
)


print()
print("RESEARCH PLANNER REFACTOR TEST")
print("==============================")


class FakeStructuredModel:

    def __init__(self):
        self.calls = []

    def invoke(
        self,
        messages,
    ) -> ResearchPlan:

        self.calls.append(
            messages
        )

        return ResearchPlan(
            topic="Test topic",
            questions=[
                ResearchQuestionPlan(
                    category="Test",
                    question=(
                        "What should be investigated?"
                    ),
                    rationale=(
                        "Used to test the "
                        "ResearchPlanner contract."
                    ),
                )
            ],
        )


#
# Construct ResearchPlanner without creating a real
# LangChain chat model. The test concerns our
# planner behaviour, not LangChain.
#

planner = ResearchPlanner.__new__(
    ResearchPlanner
)

fake_model = FakeStructuredModel()

planner.structured_model = fake_model


topic = (
    "The effect of Bitcoin mining "
    "on energy systems"
)

scope = (
    "Focus specifically on electricity pricing, "
    "grid incentives, and renewable-energy "
    "investment."
)


#
# TEST 1
# Direct create_plan() with scope.
#

print()
print("TEST 1 - CREATE PLAN WITH SCOPE")
print("-------------------------------")


plan = planner.create_plan(
    topic=topic,
    scope=scope,
)


assert isinstance(
    plan,
    ResearchPlan,
)

assert len(
    fake_model.calls
) == 1


messages = fake_model.calls[-1]

human_message = messages[1].content


assert topic in human_message

assert scope in human_message

assert (
    "Persistent research scope:"
    in human_message
)


print(
    "Direct create_plan(): PASSED"
)

print(
    "Topic passed to model: PASSED"
)

print(
    "Scope passed to model: PASSED"
)


#
# TEST 2
# LangGraph adapter with scope.
#

print()
print("TEST 2 - LANGGRAPH ADAPTER")
print("--------------------------")


result = planner(
    {
        "topic": topic,
        "scope": scope,
    }
)


assert "research_plan" in result

assert isinstance(
    result["research_plan"],
    ResearchPlan,
)

assert len(
    fake_model.calls
) == 2


messages = fake_model.calls[-1]

human_message = messages[1].content


assert topic in human_message

assert scope in human_message


print(
    "__call__() delegation: PASSED"
)


#
# TEST 3
# Existing graph states without a scope key must
# remain supported.
#

print()
print("TEST 3 - MISSING SCOPE")
print("----------------------")


result = planner(
    {
        "topic": topic,
    }
)


messages = fake_model.calls[-1]

human_message = messages[1].content


assert (
    "No additional persistent "
    "research scope has been defined."
    in human_message
)


print(
    "Missing scope compatibility: PASSED"
)


#
# TEST 4
# Blank scope is equivalent to no scope.
#

print()
print("TEST 4 - BLANK SCOPE")
print("--------------------")


planner.create_plan(
    topic=topic,
    scope="   ",
)


messages = fake_model.calls[-1]

human_message = messages[1].content


assert (
    "No additional persistent "
    "research scope has been defined."
    in human_message
)


print(
    "Blank scope normalization: PASSED"
)


#
# TEST 5
# Empty topics must fail before model invocation.
#

print()
print("TEST 5 - EMPTY TOPIC")
print("--------------------")


calls_before = len(
    fake_model.calls
)

try:

    planner.create_plan(
        topic="   ",
        scope=scope,
    )

except ValueError as exc:

    assert (
        str(exc)
        == "Research topic cannot be empty."
    )

else:

    raise AssertionError(
        "Expected empty topic to be rejected."
    )


assert len(
    fake_model.calls
) == calls_before


print(
    "Empty topic rejection: PASSED"
)

print(
    "Model not invoked for empty topic: PASSED"
)


print()
print("==============================")
print("PASS")
print("==============================")

print(
    "ResearchPlanner capability and "
    "LangGraph adapter contracts preserved."
)