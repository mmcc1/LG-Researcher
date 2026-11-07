
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from sqlalchemy import text

from application.research_job_worker import (
    ResearchJobWorker,
)

from persistence.models import (
    ResearchQuestion,
    ResearchReportEntity,
)

from persistence.report_repository import (
    ReportRepository,
)

from persistence.research_job_repository import (
    ResearchJobRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from test_research_workflow_user_questions_sql import (
    create_planning_service,
    create_planning_test_graph,
    create_submitted_research_session,
    test_environment,
)


@pytest.fixture
def reporting_environment(test_environment):

    Session, user_id = test_environment

    try:

        yield Session, user_id

    finally:

        with Session() as db:

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
                        DELETE FROM dbo.research_reports
                        WHERE research_session_id = :session_id
                    """),
                    {
                        "session_id": session_id,
                    },
                )

            db.commit()


def prepare_reporting_session(
    Session,
    user_id,
):

    original_questions = [
        "How could quantum computing threaten Bitcoin?",
    ]

    session_id = create_submitted_research_session(
        Session=Session,
        user_id=user_id,
        original_questions=original_questions,
    )

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    with Session() as db:

        research_session = (
            ResearchSessionRepository(db).get(
                session_id
            )
        )

        assert research_session is not None

        question = ResearchQuestion(
            research_session_id=session_id,
            category="technical",
            question=original_questions[0],
            rationale="Integration test question.",
            status="reviewed",
            created_at=now,
            updated_at=now,
        )

        db.add(question)

        research_session.status = "reporting"
        research_session.updated_at = now

        report = ResearchReportEntity(
            research_session_id=session_id,
            title="Quantum Computing and Bitcoin",
            executive_summary=(
                "A test report examining quantum "
                "computing risks to Bitcoin."
            ),
            conclusions=(
                "Post-quantum migration requires "
                "careful technical planning."
            ),
            created_at=now,
        )

        db.add(report)

        db.commit()

    return session_id


def get_job_state(
    Session,
    session_id,
):

    with Session() as db:

        row = db.execute(
            text("""
                SELECT
                    id,
                    status,
                    research_session_id,
                    lease_version,
                    completed_at
                FROM dbo.research_jobs
                WHERE research_session_id = :session_id
            """),
            {
                "session_id": session_id,
            },
        ).one()

    return {
        "job_id": row[0],
        "status": row[1],
        "session_id": row[2],
        "lease_version": row[3],
        "completed_at": row[4],
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


def create_reporting_graph(
    Session,
):

    graph, planner_model = create_planning_test_graph(
        Session=Session,
        original_questions=[
            "How could quantum computing threaten Bitcoin?",
        ],
        additional_question=(
            "What migration strategies are available?"
        ),
        fail_if_planner_called=True,
    )

    return graph, planner_model


def create_worker(
    Session,
    graph,
):

    workflow_service = create_planning_service(
        Session=Session,
        graph=graph,
    )

    worker = ResearchJobWorker(
        session_factory=Session,
        workflow_service=workflow_service,
        lease_duration_seconds=120,
        heartbeat_interval_seconds=30.0,
    )

    return worker


def test_worker_completes_existing_report(
    reporting_environment,
):

    Session, user_id = reporting_environment

    session_id = prepare_reporting_session(
        Session=Session,
        user_id=user_id,
    )

    initial_job = get_job_state(
        Session=Session,
        session_id=session_id,
    )

    assert initial_job["status"] == "claimed"

    expire_job_lease(
        Session=Session,
        job_id=initial_job["job_id"],
    )

    graph, planner_model = create_reporting_graph(
        Session=Session,
    )

    worker = create_worker(
        Session=Session,
        graph=graph,
    )

    completed_job_id = worker.process_next()

    assert str(completed_job_id) == str(
        initial_job["job_id"]
    )

    with Session() as db:

        session = ResearchSessionRepository(db).get(
            session_id
        )

        persisted_report = ReportRepository(
            db
        ).get_for_session(
            session_id
        )

        assert session is not None
        assert session.status == "completed"

        assert persisted_report is not None

        assert persisted_report.title == (
            "Quantum Computing and Bitcoin"
        )

    completed_job = get_job_state(
        Session=Session,
        session_id=session_id,
    )

    assert completed_job["status"] == "completed"
    assert completed_job["completed_at"] is not None

    assert (
        completed_job["lease_version"]
        > initial_job["lease_version"]
    )

    planner_model.invoke.assert_not_called()


def test_completed_session_is_finalized_without_graph_execution(
    reporting_environment,
):

    Session, user_id = reporting_environment

    session_id = prepare_reporting_session(
        Session=Session,
        user_id=user_id,
    )

    initial_job = get_job_state(
        Session=Session,
        session_id=session_id,
    )

    graph, planner_model = create_reporting_graph(
        Session=Session,
    )

    workflow_service = create_planning_service(
        Session=Session,
        graph=graph,
    )

    workflow_service.execute_existing(
        session_id=session_id,
    )

    with Session() as db:

        session = ResearchSessionRepository(db).get(
            session_id
        )

        assert session is not None
        assert session.status == "completed"

    unfinished_job = get_job_state(
        Session=Session,
        session_id=session_id,
    )

    assert unfinished_job["status"] == "claimed"
    assert unfinished_job["completed_at"] is None

    expire_job_lease(
        Session=Session,
        job_id=initial_job["job_id"],
    )

    graph_that_must_not_run = Mock()

    recovery_worker = create_worker(
        Session=Session,
        graph=graph_that_must_not_run,
    )

    completed_job_id = recovery_worker.process_next()

    assert str(completed_job_id) == str(
        initial_job["job_id"]
    )

    graph_that_must_not_run.invoke.assert_not_called()

    completed_job = get_job_state(
        Session=Session,
        session_id=session_id,
    )

    assert completed_job["status"] == "completed"
    assert completed_job["completed_at"] is not None

    assert (
        completed_job["session_id"]
        == session_id
    )

    planner_model.invoke.assert_not_called()
