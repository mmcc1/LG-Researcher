
from unittest.mock import Mock

from domain.research_plan import (
    ResearchPlan,
    ResearchQuestionPlan,
)

from agents.research_planner import (
    ResearchPlanner,
)


def test_user_questions_are_preserved():

    user_question = (
        "How does Shor's algorithm threaten "
        "Bitcoin's ECDSA signatures?"
    )

    generated_plan = ResearchPlan(
        topic="Quantum computing and Bitcoin",
        questions=[
            ResearchQuestionPlan(
                category="Cryptography",
                question=user_question.lower(),
                rationale="Explains the signature threat.",
            ),
            ResearchQuestionPlan(
                category="Migration",
                question=(
                    "How could Bitcoin migrate "
                    "to post-quantum signatures?"
                ),
                rationale=(
                    "Investigates possible migration paths."
                ),
            ),
        ],
    )

    model = Mock()

    structured_model = Mock()
    structured_model.invoke.return_value = generated_plan

    model.with_structured_output.return_value = (
        structured_model
    )

    planner = ResearchPlanner(
        model=model
    )

    result = planner.create_plan(
        topic="Quantum computing and Bitcoin",
        user_questions=[
            user_question
        ],
    )

    assert result.topic == (
        "Quantum computing and Bitcoin"
    )

    assert len(result.questions) == 2

    assert result.questions[0].question == (
        user_question
    )

    assert result.questions[0].category == (
        "Cryptography"
    )

    assert result.questions[1].question == (
        "How could Bitcoin migrate "
        "to post-quantum signatures?"
    )


def test_missing_user_question_is_restored():

    user_question = (
        "What happens to exposed Bitcoin "
        "public keys under a quantum attack?"
    )

    generated_plan = ResearchPlan(
        topic="Quantum computing and Bitcoin",
        questions=[
            ResearchQuestionPlan(
                category="Cryptography",
                question="How does Shor's algorithm work?",
                rationale="Explains the algorithm.",
            ),
        ],
    )

    model = Mock()

    structured_model = Mock()
    structured_model.invoke.return_value = generated_plan

    model.with_structured_output.return_value = (
        structured_model
    )

    planner = ResearchPlanner(
        model=model
    )

    result = planner.create_plan(
        topic="Quantum computing and Bitcoin",
        user_questions=[
            user_question
        ],
    )

    assert len(result.questions) == 2

    assert result.questions[0].question == (
        user_question
    )

    assert result.questions[0].category == (
        "user_requested"
    )

    assert result.questions[1].question == (
        "How does Shor's algorithm work?"
    )
