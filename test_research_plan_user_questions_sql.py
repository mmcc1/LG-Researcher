
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agents.research_planner import ResearchPlanner

from domain.research_plan import (
    ResearchPlan,
    ResearchQuestionPlan,
)

from nodes.save_research_plan import SaveResearchPlanNode

from persistence.database import engine

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from sqlalchemy import create_engine, text


TEST_DATABASE = "LGResearcher_Test"


@pytest.fixture
def test_environment():

    test_url = engine.url.set(
        database=TEST_DATABASE
    )

    test_engine = create_engine(
        test_url,
        echo=False,
    )

    Session = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    session_id = None

    try:

        with Session() as db:

            repository = ResearchSessionRepository(db)

            research_session = repository.create(
                topic="Quantum computing and Bitcoin",
                scope="Cryptographic threats and mitigations",
            )

            session_id = research_session.id

        yield Session, session_id

    finally:

        if session_id is not None:

            with Session() as db:

                db.execute(
                    text("""
                        DELETE FROM dbo.research_questions
                        WHERE research_session_id = :session_id
                    """),
                    {
                        "session_id": session_id,
                    },
                )

                db.execute(
                    text("""
                        DELETE FROM dbo.research_sessions
                        WHERE id = :session_id
                    """),
                    {
                        "session_id": session_id,
                    },
                )

                db.commit()

        test_engine.dispose()


def test_user_questions_persisted_without_duplication(
    test_environment,
):

    Session, session_id = test_environment

    original_questions = [
        "How does Shor's algorithm threaten Bitcoin?",
        "What post-quantum signatures could Bitcoin adopt?",
    ]

    additional_question = (
        "What migration challenges would Bitcoin face "
        "when adopting post-quantum signatures?"
    )

    model_plan = ResearchPlan(
        topic="Quantum computing and Bitcoin",
        questions=[
            ResearchQuestionPlan(
                category="cryptography",
                question=original_questions[0],
                rationale="Assess the threat to existing signatures.",
            ),
            ResearchQuestionPlan(
                category="migration",
                question=additional_question,
                rationale="Identify migration risks.",
            ),
        ],
    )

    model = Mock()

    structured_model = Mock()

    structured_model.invoke.return_value = model_plan

    model.with_structured_output.return_value = (
        structured_model
    )

    planner = ResearchPlanner(
        model=model
    )

    planning_result = planner(
        {
            "session_id": session_id,
            "topic": "Quantum computing and Bitcoin",
            "scope": "Cryptographic threats and mitigations",
            "user_questions": original_questions,
        }
    )

    plan = planning_result["research_plan"]

    assert [
        question.question
        for question in plan.questions
    ] == [
        original_questions[0],
        original_questions[1],
        additional_question,
    ]

    with Session() as db:

        lease = ExecutionLeaseRepository(db).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    try:

        with Session() as db:

            repository = ResearchSessionRepository(db)

            repository.prepare_execution_fenced(
                session_id=session_id,
                lease=lease,
                resume=False,
            )

        save_node = SaveResearchPlanNode(
            session_factory=Session
        )

        state = {
            "session_id": session_id,
            "research_plan": plan,
        }

        config = {
            "configurable": {
                "execution_lease": lease,
            },
        }

        save_node(
            state,
            config,
        )

        with Session() as db:

            repository = ResearchSessionRepository(db)

            persisted_questions = repository.get_questions(
                session_id
            )

            research_session = repository.get(
                session_id
            )

            assert research_session.status == "planned"

            assert [
                question.question
                for question in persisted_questions
            ] == [
                original_questions[0],
                original_questions[1],
                additional_question,
            ]

        save_node(
            state,
            config,
        )

        with Session() as db:

            repository = ResearchSessionRepository(db)

            persisted_questions = repository.get_questions(
                session_id
            )

            assert len(persisted_questions) == 3

        conflicting_plan = ResearchPlan(
            topic=plan.topic,
            questions=[
                ResearchQuestionPlan(
                    category="different",
                    question="An unrelated replacement question?",
                    rationale="Test conflicting persistence.",
                ),
            ],
        )

        with pytest.raises(
            ValueError,
            match="Research plan differs",
        ):

            save_node(
                {
                    "session_id": session_id,
                    "research_plan": conflicting_plan,
                },
                config,
            )

        with Session() as db:

            repository = ResearchSessionRepository(db)

            persisted_questions = repository.get_questions(
                session_id
            )

            assert [
                question.question
                for question in persisted_questions
            ] == [
                original_questions[0],
                original_questions[1],
                additional_question,
            ]

    finally:

        with Session() as db:

            ExecutionLeaseRepository(db).release(
                lease
            )
