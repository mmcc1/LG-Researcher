from domain.search import (
    SearchPlan,
    SearchQuery,
)

from agents.search_planner import (
    SearchPlanner,
)


class FakeStructuredModel:

    def __init__(
        self,
        owner,
    ):
        self.owner = owner

    def invoke(
        self,
        messages,
    ):
        self.owner.messages = messages

        return SearchPlan(
            queries=[
                SearchQuery(
                    query=(
                        "test counter evidence query"
                    ),
                    rationale=(
                        "Test query."
                    ),
                )
            ]
        )


class FakeModel:

    def __init__(
        self,
    ):
        self.messages = None

    def with_structured_output(
        self,
        schema,
    ):
        return FakeStructuredModel(
            self
        )


print()
print(
    "SEARCH PLANNER EVIDENCE CONTEXT TEST"
)
print(
    "===================================="
)


fake_model = FakeModel()

planner = SearchPlanner(
    model=fake_model
)


evidence_context = (
    "Existing research claims:\n"
    "1. SHA-256 alone prevents "
    "double-spending.\n"
    "2. Collision resistance alone "
    "provides Bitcoin consensus security."
)


#
# Counter-evidence should receive the
# evidence context.
#

result = planner.create_plan(
    topic=(
        "What role does SHA-256 play "
        "in Bitcoin proof-of-work?"
    ),
    question=(
        "How does SHA-256 enable "
        "Bitcoin proof-of-work?"
    ),
    purpose="counter_evidence",
    instructions=(
        "Look for technical evidence "
        "that qualifies these claims."
    ),
    existing_evidence_context=(
        evidence_context
    ),
)


assert len(result.queries) == 1


system_message = (
    fake_model.messages[0].content
)

human_message = (
    fake_model.messages[1].content
)


print()
print("COUNTER-EVIDENCE PROMPT")
print("-----------------------")
print(human_message)


assert (
    evidence_context
    in human_message
)

assert (
    "Existing research claims to "
    "challenge or qualify:"
    in human_message
)

assert (
    "propositions to test"
    in system_message
)


#
# Initial research must NOT receive the
# evidence context.
#

planner.create_plan(
    topic="Test topic",
    question="Test question",
    purpose="initial",
    existing_evidence_context=(
        evidence_context
    ),
)


initial_human_message = (
    fake_model.messages[1].content
)


print()
print("INITIAL PROMPT")
print("--------------")
print(initial_human_message)


assert (
    evidence_context
    not in initial_human_message
)

assert (
    "Existing research claims to "
    "challenge or qualify:"
    not in initial_human_message
)


#
# Deeper research must also NOT receive
# the evidence context.
#

planner.create_plan(
    topic="Test topic",
    question="Test question",
    purpose="deeper_research",
    instructions=(
        "Investigate implementation "
        "details."
    ),
    existing_evidence_context=(
        evidence_context
    ),
)


deeper_human_message = (
    fake_model.messages[1].content
)


print()
print("DEEPER-RESEARCH PROMPT")
print("----------------------")
print(deeper_human_message)


assert (
    evidence_context
    not in deeper_human_message
)


#
# Counter-evidence must still work when
# no evidence context is available.
#

planner.create_plan(
    topic="Test topic",
    question="Test question",
    purpose="counter_evidence",
)


counter_without_evidence = (
    fake_model.messages[1].content
)


assert (
    "No existing research claims "
    "were supplied."
    in counter_without_evidence
)


print()
print(
    "===================================="
)
print("PASS")
print(
    "===================================="
)