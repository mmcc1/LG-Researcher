
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from langgraph.checkpoint.memory import InMemorySaver

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from domain.research_plan import (
    ResearchPlan,
    ResearchQuestionPlan,
)

from graph.research_graph import (
    create_research_graph,
)

from models.agent_models import (
    AgentModels,
)

from persistence.database import engine

from persistence.models import UserAccount

from persistence.research_job_repository import (
    ResearchJobRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)



TEST_DATABASE = "LGResearcher_Test"


class CapturingGraph:

    def __init__(self):

        self.invocations = []

    def invoke(
        self,
        state,
        config,
    ):

        self.invocations.append(
            {
                "state": dict(state),
                "config": config,
            }
        )

        return {
            "captured": True,
        }


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

    user_id = str(uuid4())

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    with Session() as db:

        user = UserAccount(
            id=user_id,
            username=f"test_{user_id[:8]}",
            email=f"{user_id}@example.invalid",
            password_hash="integration-test-only",
            is_active=True,
            email_reports_enabled=False,
            created_at=now,
            last_login_at=None,
        )

        db.add(user)
        db.commit()

    try:

        yield Session, user_id

    finally:

        with Session() as db:

            db.execute(
                text("""
                    DELETE q
                    FROM dbo.research_job_questions AS q
                    INNER JOIN dbo.research_jobs AS j
                        ON j.id = q.research_job_id
                    WHERE j.user_id = :user_id
                """),
                {
                    "user_id": user_id,
                },
            )

            session_ids = db.execute(
                text("""
                    SELECT research_session_id
                    FROM dbo.research_jobs
                    WHERE user_id = :user_id
                      AND research_session_id IS NOT NULL
                """),
                {
                    "user_id": user_id,
                },
            ).scalars().all()

            for session_id in session_ids:

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
                    DELETE FROM dbo.research_jobs
                    WHERE user_id = :user_id
                """),
                {
                    "user_id": user_id,
                },
            )

            for session_id in session_ids:

                db.execute(
                    text("""
                        DELETE FROM dbo.research_sessions
                        WHERE id = :session_id
                    """),
                    {
                        "session_id": session_id,
                    },
                )

            db.execute(
                text("""
                    DELETE FROM dbo.users
                    WHERE id = :user_id
                """),
                {
                    "user_id": user_id,
                },
            )

            db.commit()

        test_engine.dispose()


def create_submitted_research_session(
    Session,
    user_id,
    original_questions,
):

    with Session() as db:

        repository = ResearchJobRepository(db)

        job_id = repository.create_draft(
            user_id=user_id,
            topic="Quantum computing and Bitcoin",
            scope="Cryptographic threats and mitigations",
        )

        for question in original_questions:

            question_id = repository.add_draft_question(
                job_id=job_id,
                user_id=user_id,
                question=question,
            )

            assert question_id is not None

        assert repository.submit_draft(
            job_id=job_id,
            user_id=user_id,
        )

        claimed = repository.claim_next()

        assert claimed is not None
        assert claimed.job_id == job_id

        session_id = repository.associate_session(
            claimed.lease
        )

    return session_id


def test_submitted_questions_reach_workflow_graph(
    test_environment,
):

    Session, user_id = test_environment

    original_questions = [
        "How does Shor's algorithm threaten Bitcoin?",
        "What post-quantum signatures could Bitcoin adopt?",
    ]

    session_id = create_submitted_research_session(
        Session=Session,
        user_id=user_id,
        original_questions=original_questions,
    )

    graph = CapturingGraph()

    service = ResearchWorkflowService(
        graph=graph,
        session_factory=Session,
        lease_duration_seconds=120,
        heartbeat_interval_seconds=30.0,
    )

    result = service.execute_existing(
        session_id=session_id
    )

    assert result.session_id == session_id

    assert len(graph.invocations) == 1

    first_state = graph.invocations[0]["state"]

    assert first_state["session_id"] == session_id
    assert first_state["resume"] is False

    assert first_state["user_questions"] == (
        original_questions
    )

    assert first_state["topic"] == (
        "Quantum computing and Bitcoin"
    )

    assert first_state["scope"] == (
        "Cryptographic threats and mitigations"
    )


def test_production_graph_persists_submitted_questions(
    test_environment,
):

    Session, user_id = test_environment

    original_questions = [
        "How does Shor's algorithm threaten Bitcoin?",
        "What post-quantum signatures could Bitcoin adopt?",
    ]

    additional_question = (
        "What migration challenges would Bitcoin face "
        "when adopting post-quantum signatures?"
    )

    session_id = create_submitted_research_session(
        Session=Session,
        user_id=user_id,
        original_questions=original_questions,
    )

    model_plan = ResearchPlan(
        topic="Quantum computing and Bitcoin",
        questions=[
            ResearchQuestionPlan(
                category="cryptography",
                question=original_questions[0],
                rationale="Assess the existing signature threat.",
            ),
            ResearchQuestionPlan(
                category="migration",
                question=additional_question,
                rationale="Identify migration challenges.",
            ),
        ],
    )

    planner_model = Mock()

    structured_model = Mock()

    structured_model.invoke.return_value = (
        model_plan
    )

    planner_model.with_structured_output.return_value = (
        structured_model
    )

    unused_model = Mock()

    models = AgentModels(
        planner=planner_model,
        researcher=unused_model,
        summariser=unused_model,
        reviewer=unused_model,
        reporter=unused_model,
        controller=unused_model,
    )

    checkpointer = InMemorySaver()

    graph = create_research_graph(
        models=models,
        session_factory=Session,
        search_provider=Mock(),
        document_retriever=Mock(),
        document_extractor=Mock(),
        interrupt_after=[
            "save_research_plan"
        ],
        checkpointer=checkpointer,
    )

    service = ResearchWorkflowService(
        graph=graph,
        session_factory=Session,
        lease_duration_seconds=120,
        heartbeat_interval_seconds=30.0,
    )

    result = service.execute_existing(
        session_id=session_id
    )

    assert result.session_id == session_id

    with Session() as db:

        repository = ResearchSessionRepository(db)

        research_session = repository.get(
            session_id
        )

        questions = repository.get_questions(
            session_id
        )

        assert research_session.status == "planned"

        assert [
            question.question
            for question in questions
        ] == [
            original_questions[0],
            original_questions[1],
            additional_question,
        ]

        assert len(questions) == 3

    structured_model.invoke.assert_called_once()



class LeaseRecordingGraph:

    def __init__(
        self,
        graph,
    ):

        self.graph = graph
        self.leases = []

    def invoke(
        self,
        state,
        config,
    ):

        lease = config["configurable"]["execution_lease"]

        self.leases.append(lease)

        return self.graph.invoke(
            state,
            config=config,
        )


def create_planning_test_graph(
    Session,
    original_questions,
    additional_question,
    interrupt_after=None,
    interrupt_before=None,
    fail_if_planner_called=False,
):

    model_plan = ResearchPlan(
        topic="Quantum computing and Bitcoin",
        questions=[
            ResearchQuestionPlan(
                category="cryptography",
                question=original_questions[0],
                rationale="Assess the existing signature threat.",
            ),
            ResearchQuestionPlan(
                category="migration",
                question=additional_question,
                rationale="Identify migration challenges.",
            ),
        ],
    )

    planner_model = Mock()
    structured_model = Mock()

    if fail_if_planner_called:

        structured_model.invoke.side_effect = (
            AssertionError(
                "Research planner must not run during recovery."
            )
        )

    else:

        structured_model.invoke.return_value = model_plan

    planner_model.with_structured_output.return_value = (
        structured_model
    )

    unused_model = Mock()

    models = AgentModels(
        planner=planner_model,
        researcher=unused_model,
        summariser=unused_model,
        reviewer=unused_model,
        reporter=unused_model,
        controller=unused_model,
    )

    graph = create_research_graph(
        models=models,
        session_factory=Session,
        search_provider=Mock(),
        document_retriever=Mock(),
        document_extractor=Mock(),
        interrupt_before=interrupt_before,
        interrupt_after=interrupt_after,
        checkpointer=InMemorySaver(),
    )

    return graph, structured_model


def create_planning_service(
    Session,
    graph,
):

    return ResearchWorkflowService(
        graph=graph,
        session_factory=Session,
        lease_duration_seconds=120,
        heartbeat_interval_seconds=30.0,
    )


def get_persisted_plan_state(
    Session,
    session_id,
):

    with Session() as db:

        repository = ResearchSessionRepository(db)

        research_session = repository.get(
            session_id
        )

        questions = repository.get_questions(
            session_id
        )

        return (
            research_session.status,
            [
                question.question
                for question in questions
            ],
        )


def test_recovery_before_plan_persistence(
    test_environment,
):

    Session, user_id = test_environment

    original_questions = [
        "How does Shor's algorithm threaten Bitcoin?",
        "What post-quantum signatures could Bitcoin adopt?",
    ]

    additional_question = (
        "What migration challenges would Bitcoin face "
        "when adopting post-quantum signatures?"
    )

    expected_questions = [
        *original_questions,
        additional_question,
    ]

    session_id = create_submitted_research_session(
        Session=Session,
        user_id=user_id,
        original_questions=original_questions,
    )

    interrupted_graph, first_model = (
        create_planning_test_graph(
            Session=Session,
            original_questions=original_questions,
            additional_question=additional_question,
            interrupt_after=[
                "plan_research"
            ],
        )
    )

    first_service = create_planning_service(
        Session=Session,
        graph=interrupted_graph,
    )

    first_service.execute_existing(
        session_id=session_id
    )

    status, questions = get_persisted_plan_state(
        Session=Session,
        session_id=session_id,
    )

    assert status == "planning"
    assert questions == []

    first_model.invoke.assert_called_once()

    recovery_graph, recovery_model = (
        create_planning_test_graph(
            Session=Session,
            original_questions=original_questions,
            additional_question=additional_question,
            interrupt_after=[
                "save_research_plan"
            ],
        )
    )

    recovery_service = create_planning_service(
        Session=Session,
        graph=recovery_graph,
    )

    recovery_result = recovery_service.execute_existing(
        session_id=session_id
    )

    assert recovery_result.session_id == session_id

    status, questions = get_persisted_plan_state(
        Session=Session,
        session_id=session_id,
    )

    assert status == "planned"
    assert questions == expected_questions

    recovery_model.invoke.assert_called_once()


def test_recovery_after_plan_persistence(
    test_environment,
):

    Session, user_id = test_environment

    original_questions = [
        "How does Shor's algorithm threaten Bitcoin?",
        "What post-quantum signatures could Bitcoin adopt?",
    ]

    additional_question = (
        "What migration challenges would Bitcoin face "
        "when adopting post-quantum signatures?"
    )

    expected_questions = [
        *original_questions,
        additional_question,
    ]

    session_id = create_submitted_research_session(
        Session=Session,
        user_id=user_id,
        original_questions=original_questions,
    )

    first_graph, first_model = (
        create_planning_test_graph(
            Session=Session,
            original_questions=original_questions,
            additional_question=additional_question,
            interrupt_after=[
                "save_research_plan"
            ],
        )
    )

    first_service = create_planning_service(
        Session=Session,
        graph=first_graph,
    )

    first_service.execute_existing(
        session_id=session_id
    )

    status, questions = get_persisted_plan_state(
        Session=Session,
        session_id=session_id,
    )

    assert status == "planned"
    assert questions == expected_questions

    first_model.invoke.assert_called_once()

    recovery_graph, recovery_model = (
        create_planning_test_graph(
            Session=Session,
            original_questions=original_questions,
            additional_question=additional_question,
            fail_if_planner_called=True,
            interrupt_before=[
                "select_question"
            ],
        )
    )

    recovery_service = create_planning_service(
        Session=Session,
        graph=recovery_graph,
    )

    recovery_service.execute_existing(
        session_id=session_id
    )

    recovery_model.invoke.assert_not_called()

    status, questions = get_persisted_plan_state(
        Session=Session,
        session_id=session_id,
    )

    assert status == "planned"
    assert questions == expected_questions
    assert len(questions) == 3


def test_recovery_uses_new_execution_lease(
    test_environment,
):

    Session, user_id = test_environment

    original_questions = [
        "How does Shor's algorithm threaten Bitcoin?",
        "What post-quantum signatures could Bitcoin adopt?",
    ]

    additional_question = (
        "What migration challenges would Bitcoin face "
        "when adopting post-quantum signatures?"
    )

    expected_questions = [
        *original_questions,
        additional_question,
    ]

    session_id = create_submitted_research_session(
        Session=Session,
        user_id=user_id,
        original_questions=original_questions,
    )

    first_graph, first_model = (
        create_planning_test_graph(
            Session=Session,
            original_questions=original_questions,
            additional_question=additional_question,
            interrupt_after=[
                "save_research_plan"
            ],
        )
    )

    first_recording_graph = LeaseRecordingGraph(
        first_graph
    )

    first_service = create_planning_service(
        Session=Session,
        graph=first_recording_graph,
    )

    first_service.execute_existing(
        session_id=session_id
    )

    assert len(first_recording_graph.leases) == 1

    first_lease = first_recording_graph.leases[0]

    recovery_graph, recovery_model = (
        create_planning_test_graph(
            Session=Session,
            original_questions=original_questions,
            additional_question=additional_question,
            fail_if_planner_called=True,
            interrupt_before=[
                "select_question"
            ],
        )
    )

    recovery_recording_graph = LeaseRecordingGraph(
        recovery_graph
    )

    recovery_service = create_planning_service(
        Session=Session,
        graph=recovery_recording_graph,
    )

    recovery_service.execute_existing(
        session_id=session_id
    )

    assert len(recovery_recording_graph.leases) == 1

    recovery_lease = recovery_recording_graph.leases[0]

    assert recovery_lease.session_id == session_id
    assert recovery_lease != first_lease

    recovery_model.invoke.assert_not_called()

    status, questions = get_persisted_plan_state(
        Session=Session,
        session_id=session_id,
    )

    assert status == "planned"
    assert questions == expected_questions
    assert len(questions) == 3
