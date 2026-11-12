
from unittest.mock import Mock

import pytest

from sqlalchemy import text

from application.research_job_worker import (
    ResearchJobNotCompleted,
    ResearchJobWorker,
)

from persistence.research_job_repository import (
    ResearchJobRepository,
)

from test_research_workflow_user_questions_sql import (
    create_planning_service,
    create_planning_test_graph,
    get_persisted_plan_state,
    test_environment,
)


def create_submitted_job(
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

        submitted = repository.submit_draft(
            job_id=job_id,
            user_id=user_id,
        )

        assert submitted

    return job_id


def get_job_state(
    Session,
    job_id,
):

    with Session() as db:

        row = db.execute(
            text("""
                SELECT
                    status,
                    research_session_id,
                    lease_version,
                    execution_owner,
                    lease_expires_at,
                    completed_at
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job_id,
            },
        ).one()

    return {
        "status": row[0],
        "session_id": row[1],
        "lease_version": row[2],
        "execution_owner": row[3],
        "lease_expires_at": row[4],
        "completed_at": row[5],
    }


def expire_job_lease(
    Session,
    job_id,
):

    with Session() as db:

        db.execute(
            text("""
                UPDATE dbo.research_jobs
                SET lease_expires_at = DATEADD(
                    second,
                    -10,
                    SYSUTCDATETIME()
                )
                WHERE id = :job_id
            """),
            {
                "job_id": job_id,
            },
        )

        db.commit()


def create_worker(
    Session,
    graph,
):

    service = create_planning_service(
        Session=Session,
        graph=graph,
    )

    worker = ResearchJobWorker(
        session_factory=Session,
        workflow_service=service,
        lease_duration_seconds=120,
        heartbeat_interval_seconds=30.0,
    )

    return worker


def test_worker_recovers_persisted_plan_without_replanning(
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

    job_id = create_submitted_job(
        Session=Session,
        user_id=user_id,
        original_questions=original_questions,
    )

    first_graph, first_model = create_planning_test_graph(
        Session=Session,
        original_questions=original_questions,
        additional_question=additional_question,
        interrupt_after=[
            "save_research_plan",
        ],
    )

    first_worker = create_worker(
        Session=Session,
        graph=first_graph,
    )

    with pytest.raises(
        ResearchJobNotCompleted,
        match="could not be finalized",
    ):

        first_worker.process_next()

    first_job_state = get_job_state(
        Session=Session,
        job_id=job_id,
    )

    assert first_job_state["status"] == "claimed"
    assert first_job_state["session_id"] is not None
    assert first_job_state["execution_owner"] is not None
    assert first_job_state["completed_at"] is None

    session_id = first_job_state["session_id"]

    status, questions = get_persisted_plan_state(
        Session=Session,
        session_id=session_id,
    )

    assert status == "planned"
    assert questions == expected_questions
    assert len(questions) == 3

    first_model.invoke.assert_called_once()

    original_lease_version = (
        first_job_state["lease_version"]
    )

    expire_job_lease(
        Session=Session,
        job_id=job_id,
    )

    recovery_graph, recovery_model = (
        create_planning_test_graph(
            Session=Session,
            original_questions=original_questions,
            additional_question=additional_question,
            fail_if_planner_called=True,
            interrupt_before=[
                "select_question",
            ],
        )
    )

    recovery_worker = create_worker(
        Session=Session,
        graph=recovery_graph,
    )

    with pytest.raises(
        ResearchJobNotCompleted,
        match="could not be finalized",
    ):

        recovery_worker.process_next()

    recovered_job_state = get_job_state(
        Session=Session,
        job_id=job_id,
    )

    assert recovered_job_state["status"] == "claimed"

    assert (
        recovered_job_state["session_id"]
        == session_id
    )

    assert (
        recovered_job_state["lease_version"]
        > original_lease_version
    )

    assert recovered_job_state["completed_at"] is None

    recovery_model.invoke.assert_not_called()

    recovered_status, recovered_questions = (
        get_persisted_plan_state(
            Session=Session,
            session_id=session_id,
        )
    )

    assert recovered_status == "planned"
    assert recovered_questions == expected_questions
    assert len(recovered_questions) == 3


def test_worker_passes_submitted_questions_to_graph(
    test_environment,
):

    Session, user_id = test_environment

    original_questions = [
        "How does Shor's algorithm threaten Bitcoin?",
        "What post-quantum signatures could Bitcoin adopt?",
    ]

    job_id = create_submitted_job(
        Session=Session,
        user_id=user_id,
        original_questions=original_questions,
    )

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

    graph = CapturingGraph()

    worker = create_worker(
        Session=Session,
        graph=graph,
    )

    with pytest.raises(
        ResearchJobNotCompleted,
        match="could not be finalized",
    ):

        worker.process_next()

    assert len(graph.invocations) == 1

    state = graph.invocations[0]["state"]

    job_state = get_job_state(
        Session=Session,
        job_id=job_id,
    )

    assert state["session_id"] == job_state["session_id"]
    assert state["resume"] is False
    assert state["user_questions"] == original_questions

    assert state["topic"] == (
        "Quantum computing and Bitcoin"
    )

    assert state["scope"] == (
        "Cryptographic threats and mitigations"
    )

    assert job_state["status"] == "claimed"
    assert job_state["completed_at"] is None
