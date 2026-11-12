from agents.research_planner import (
    ResearchPlanner,
)

from config import settings

from models.factory import (
    ChatModelFactory,
)


print()
print("RESEARCH PLANNER SCOPE TEST")
print("===========================")


#
# -------------------------------------------------
# Test inputs.
#
# The same broad topic is planned twice.
#
# Test 1:
#     No persistent scope.
#
# Test 2:
#     Persistent scope restricting the research
#     toward electricity-market economics.
# -------------------------------------------------
#

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
# -------------------------------------------------
# Create the real planner model.
#
# ResearchPlanner is the high-level research
# planning agent, so use planner_model.
# -------------------------------------------------
#

print()
print("MODEL")
print("-----")

print(
    f"Provider: "
    f"{settings.planner_model.provider}"
)

print(
    f"Model:    "
    f"{settings.planner_model.model_name}"
)

print(
    f"Base URL: "
    f"{settings.planner_model.base_url}"
)


model = ChatModelFactory.create(
    settings.planner_model
)

research_planner = ResearchPlanner(
    model=model
)


#
# -------------------------------------------------
# TEST 1
#
# Baseline planning with no persistent scope.
# -------------------------------------------------
#

print()
print("TEST 1 - NO PERSISTENT SCOPE")
print("============================")

print()
print(
    f"Topic: {topic}"
)

print(
    "Scope: None"
)

print()
print("Calling Qwen...")


baseline_plan = (
    research_planner.create_plan(
        topic=topic,
        scope=None,
    )
)


print()
print("BASELINE RESEARCH QUESTIONS")
print("---------------------------")


for index, planned_question in enumerate(
    baseline_plan.questions,
    start=1,
):

    print()
    print(
        f"Question {index}"
    )

    print(
        f"Category:  "
        f"{planned_question.category}"
    )

    print(
        f"Question:  "
        f"{planned_question.question}"
    )

    print(
        f"Rationale: "
        f"{planned_question.rationale}"
    )


#
# -------------------------------------------------
# TEST 2
#
# Same topic with persistent research scope.
# -------------------------------------------------
#

print()
print()
print("TEST 2 - PERSISTENT SCOPE")
print("=========================")

print()
print(
    f"Topic: {topic}"
)

print(
    f"Scope: {scope}"
)

print()
print("Calling Qwen...")


scoped_plan = (
    research_planner.create_plan(
        topic=topic,
        scope=scope,
    )
)


print()
print("SCOPED RESEARCH QUESTIONS")
print("-------------------------")


for index, planned_question in enumerate(
    scoped_plan.questions,
    start=1,
):

    print()
    print(
        f"Question {index}"
    )

    print(
        f"Category:  "
        f"{planned_question.category}"
    )

    print(
        f"Question:  "
        f"{planned_question.question}"
    )

    print(
        f"Rationale: "
        f"{planned_question.rationale}"
    )


#
# -------------------------------------------------
# Structural validation.
#
# Do not assert exact question wording or impose a
# fixed number of questions. Those are model
# decisions and should remain flexible.
# -------------------------------------------------
#

assert baseline_plan.questions, (
    "Baseline ResearchPlanner returned "
    "no research questions."
)

assert scoped_plan.questions, (
    "Scoped ResearchPlanner returned "
    "no research questions."
)


for planned_question in (
    baseline_plan.questions
):

    assert (
        planned_question.category.strip()
    )

    assert (
        planned_question.question.strip()
    )

    assert (
        planned_question.rationale.strip()
    )


for planned_question in (
    scoped_plan.questions
):

    assert (
        planned_question.category.strip()
    )

    assert (
        planned_question.question.strip()
    )

    assert (
        planned_question.rationale.strip()
    )


print()
print()
print("STRUCTURAL VALIDATION")
print("=====================")

print(
    "Baseline plan returned questions: "
    "PASSED"
)

print(
    "Scoped plan returned questions: "
    "PASSED"
)

print(
    "ResearchQuestionPlan structured "
    "output: PASSED"
)


#
# -------------------------------------------------
# Comparison.
#
# Informational only.
#
# Exact model output is nondeterministic, so we do
# not require the two plans to differ textually.
# -------------------------------------------------
#

baseline_questions = {
    item.question.strip().lower()
    for item in baseline_plan.questions
}

scoped_questions = {
    item.question.strip().lower()
    for item in scoped_plan.questions
}


print()
print("PLAN COMPARISON")
print("===============")


if (
    baseline_questions
    == scoped_questions
):

    print(
        "WARNING: The scoped and unscoped "
        "question sets are identical."
    )

    print(
        "Inspect the categories and rationales "
        "to determine whether scope influenced "
        "the research plan."
    )

else:

    print(
        "Scoped and unscoped research "
        "question sets differ."
    )


print()
print("===========================")
print("TEST COMPLETE")
print("===========================")

print(
    "Inspect the scoped questions above and "
    "verify that they remain focused on "
    "electricity pricing, grid incentives, "
    "and renewable-energy investment."
)