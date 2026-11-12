
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import pytest

from sqlalchemy import text

from agents.report_agent import ReportAgent

from application.research_job_worker import (
    ResearchJobWorker,
)

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from domain.report import (
    ResearchReport,
    ReportSection,
)

from graph.research_graph import (
    create_research_graph,
)

from models.agent_models import AgentModels

from persistence.models import UserAccount

from persistence.research_job_repository import (
    ResearchJobRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.review_repository import (
    ReviewRepository,
)

from persistence.report_repository import (
    ReportRepository,
)

from test_research_review_recovery_sql import (
    test_environment,
)

from domain.review import ResearchQuestionReview


def create_unused_model():

    model = Mock()

    structured_model = Mock()

    structured_model.invoke.side_effect = AssertionError(
        "An LLM was invoked during recovery."
    )

    model.with_structured_output.return_value = (
        structured_model
    )

    return model


def create_test_graph(
    Session,
    monkeypatch,
    report_calls,
):

    def generate_report(
        self,
        topic,
        reviewed_evidence,
    ):

        report_calls.append(
            {
                "topic": topic,
                "reviewed_evidence": reviewed_evidence,
            }
        )

        return ResearchReport(
            title="Recovered Research Report",
            executive_summary=(
                "The recovered research questions "
                "have insufficient supporting evidence."
            ),
            sections=[
                ReportSection(
                    heading="Evidence Assessment",
                    content=(
                        "Neither question has sufficient "
                        "research findings to support "
                        "substantive conclusions."
                    ),
                    reviewed_claim_ids=[],
                ),
            ],
            conclusions=(
                "Further research is required."
            ),
            limitations=[
                "No supporting research findings were available.",
            ],
        )

    monkeypatch.setattr(
        ReportAgent,
        "generate",
        generate_report,
    )

    models = AgentModels(
        planner=create_unused_model(),
        researcher=create_unused_model(),
        summariser=create_unused_model(),
        reviewer=create_unused_model(),
        reporter=create_unused_model(),
        controller=create_unused_model(),
    )

    graph = create_research_graph(
        models=models,
        session_factory=Session,
        search_provider=Mock(),
        document_retriever=Mock(),
        document_extractor=Mock(),
    )

    return graph


def create_test_user(
    Session,
):

    user_id = str(uuid4())

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    with Session() as db:

        user = UserAccount(
            id=user_id,
            username=f"graph_{user_id[:8]}",
            email=f"{user_id}@example.invalid",
            password_hash="integration-test-only",
            is_active=True,
            email_reports_enabled=False,
            created_at=now,
            last_login_at=None,
        )

        db.add(user)

        db.commit()

    return user_id


def create_failed_recovery_job(
    Session,
    user_id,
    session_ids,
):

    with Session() as db:

        repository = ResearchJobRepository(
            db
        )

        job_id = repository.submit(
            user_id=user_id,
            topic="Synthetic graph recovery assessment",
            scope="Review and reporting recovery",
        )

        claimed = repository.claim_next(
            duration_seconds=120
        )

        assert claimed is not None

        assert claimed.job_id == job_id

        session_id = repository.associate_session(
            claimed.lease
        )

        session_ids.append(
            session_id
        )

        failed = repository.fail(
            lease=claimed.lease,
            error="Synthetic interruption before review recovery.",
        )

        assert failed is True

    with Session() as db:

        repository = ResearchSessionRepository(
            db
        )

        first_question = repository.add_question(
            session_id=session_id,
            question="What evidence supports question one?",
        )

        second_question = repository.add_question(
            session_id=session_id,
            question="What evidence supports question two?",
        )

        repository.set_question_status(
            question_id=first_question.id,
            status="reviewing",
        )

        repository.set_question_status(
            question_id=second_question.id,
            status="researched",
        )

        repository.set_status(
            session_id=session_id,
            status="reviewing",
        )

        first_question_id = first_question.id

        second_question_id = second_question.id

    with Session() as db:

        repository = ResearchJobRepository(
            db
        )

        retried = repository.retry_failed(
            job_id=job_id,
            user_id=user_id,
        )

        assert retried is True

    return (
        job_id,
        session_id,
        first_question_id,
        second_question_id,
    )


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
                    execution_owner,
                    last_error
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
            "owner": row[2],
            "error": row[3],
        }


def get_review_count(
    Session,
    question_id,
):

    with Session() as db:

        return db.execute(
            text("""
                SELECT COUNT(*)
                FROM dbo.question_reviews
                WHERE research_question_id = :question_id
            """),
            {
                "question_id": question_id,
            },
        ).scalar_one()


def cleanup_test_user_and_job(
    Session,
    user_id,
):

    with Session() as db:

        db.execute(
            text("""
                DELETE FROM dbo.research_job_questions
                WHERE research_job_id IN (
                    SELECT id
                    FROM dbo.research_jobs
                    WHERE user_id = :user_id
                )
            """),
            {
                "user_id": user_id,
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


def test_full_graph_recovery(
    test_environment,
    monkeypatch,
):

    Session, session_ids = test_environment

    user_id = create_test_user(
        Session
    )

    report_calls = []

    try:

        (
            job_id,
            session_id,
            first_question_id,
            second_question_id,
        ) = create_failed_recovery_job(
            Session,
            user_id,
            session_ids,
        )

        original_job = get_job_state(
            Session,
            job_id,
        )

        assert original_job["status"] == "queued"

        assert original_job["session_id"] == session_id

        graph = create_test_graph(
            Session,
            monkeypatch,
            report_calls,
        )

        workflow_service = ResearchWorkflowService(
            graph=graph,
            session_factory=Session,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )

        worker = ResearchJobWorker(
            session_factory=Session,
            workflow_service=workflow_service,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )

        processed_job_id = worker.process_next()

        assert processed_job_id == job_id

        completed_job = get_job_state(
            Session,
            job_id,
        )

        assert completed_job["status"] == "completed"

        assert completed_job["session_id"] == session_id

        assert completed_job["owner"] is None

        with Session() as db:

            repository = ResearchSessionRepository(
                db
            )

            research_session = repository.get(
                session_id
            )

            assert research_session is not None

            assert research_session.status == "completed"

            questions = repository.get_questions(
                session_id
            )

            assert len(questions) == 2

            assert all(
                question.status == "reviewed"
                for question in questions
            )

        assert get_review_count(
            Session,
            first_question_id,
        ) == 1

        assert get_review_count(
            Session,
            second_question_id,
        ) == 1

        with Session() as db:

            repository = ReviewRepository(
                db
            )

            reviews = repository.get_for_session(
                session_id
            )

            assert len(reviews) == 2

            assert all(
                review.sufficient_evidence is False
                for review in reviews
            )

            assert all(
                len(review.reviewed_claims) == 0
                for review in reviews
            )

        assert len(report_calls) == 1

        assert report_calls[0]["topic"] == (
            "Synthetic graph recovery assessment"
        )

        assert (
            "insufficient"
            in report_calls[0]["reviewed_evidence"].lower()
            or "No research findings"
            in report_calls[0]["reviewed_evidence"]
        )

        with Session() as db:

            repository = ReportRepository(
                db
            )

            persisted_report = repository.get_for_session(
                session_id
            )

            assert persisted_report is not None

            assert persisted_report.title == (
                "Recovered Research Report"
            )

            assert len(persisted_report.sections) == 1

            assert (
                persisted_report.sections[0].reviewed_claim_ids
                == []
            )

        with Session() as db:

            report_count = db.execute(
                text("""
                    SELECT COUNT(*)
                    FROM dbo.research_reports
                    WHERE research_session_id = :session_id
                """),
                {
                    "session_id": session_id,
                },
            ).scalar_one()

        assert report_count == 1

    finally:

        cleanup_test_user_and_job(
            Session,
            user_id,
        )



def test_graph_recovers_existing_persisted_report(
    test_environment,
    monkeypatch,
):

    Session, session_ids = test_environment

    user_id = create_test_user(
        Session
    )

    report_calls = []

    try:

        (
            job_id,
            session_id,
            first_question_id,
            second_question_id,
        ) = create_failed_recovery_job(
            Session,
            user_id,
            session_ids,
        )

        #
        # The job is queued for recovery, but
        # the session is still in its review phase.
        #
        # Establish the durable state that would
        # exist after review and report persistence.
        #

        from persistence.execution_lease_repository import (
            ExecutionLeaseRepository,
        )

        with Session() as db:

            lease = ExecutionLeaseRepository(
                db
            ).acquire(
                session_id=session_id,
                duration_seconds=120,
            )

            assert lease is not None

        original_report_id = None

        try:

            for question_id in (
                first_question_id,
                second_question_id,
            ):

                with Session() as db:

                    repository = ResearchSessionRepository(
                        db
                    )

                    selected = (
                        repository.select_review_question_fenced(
                            session_id=session_id,
                            lease=lease,
                        )
                    )

                    assert selected is not None

                    assert selected.id == question_id

                with Session() as db:

                    repository = ReviewRepository(
                        db
                    )

                    repository.save_review_fenced(
                        session_id=session_id,
                        question_id=question_id,
                        review=ResearchQuestionReview(
                            answer=(
                                "Insufficient evidence to answer "
                                "the research question."
                            ),
                            reviewed_claims=[],
                            contradictions=[],
                            evidence_gaps=[
                                "No research findings were available "
                                "for this question."
                            ],
                            overall_confidence="low",
                            sufficient_evidence=False,
                        ),
                        valid_finding_ids=set(),
                        lease=lease,
                    )

            with Session() as db:

                repository = ResearchSessionRepository(
                    db
                )

                selected = (
                    repository.select_review_question_fenced(
                        session_id=session_id,
                        lease=lease,
                    )
                )

                assert selected is None

                repository.complete_review_fenced(
                    session_id=session_id,
                    lease=lease,
                )

                repository.begin_reporting_fenced(
                    session_id=session_id,
                    lease=lease,
                )

            #
            # Persist the report using the real
            # fenced repository operation.
            #
            # Do not complete the research session.
            #

            with Session() as db:

                repository = ReportRepository(
                    db
                )

                original_report_id = (
                    repository.save_report_fenced(
                        session_id=session_id,
                        report=ResearchReport(
                            title="Previously Persisted Report",
                            executive_summary=(
                                "The available evidence is "
                                "insufficient."
                            ),
                            sections=[
                                ReportSection(
                                    heading="Evidence Assessment",
                                    content=(
                                        "No supporting research "
                                        "findings were available."
                                    ),
                                    reviewed_claim_ids=[],
                                ),
                            ],
                            conclusions=(
                                "Further research is required."
                            ),
                            limitations=[
                                "No supporting findings were available.",
                            ],
                        ),
                        lease=lease,
                    )
                )

                assert original_report_id > 0

        finally:

            #
            # Simulate the previous execution ending.
            # The report remains committed to SQL.
            #

            with Session() as db:

                ExecutionLeaseRepository(
                    db
                ).release(
                    lease
                )

        #
        # Verify the interrupted durable state.
        #

        with Session() as db:

            repository = ResearchSessionRepository(
                db
            )

            research_session = repository.get(
                session_id
            )

            assert research_session.status == "reporting"

        queued_job = get_job_state(
            Session,
            job_id,
        )

        assert queued_job["status"] == "queued"

        assert queued_job["session_id"] == session_id

        #
        # Compile the actual graph.
        #
        # The deterministic Report Agent is installed,
        # but it must never be invoked in this scenario.
        #

        graph = create_test_graph(
            Session,
            monkeypatch,
            report_calls,
        )

        workflow_service = ResearchWorkflowService(
            graph=graph,
            session_factory=Session,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )

        worker = ResearchJobWorker(
            session_factory=Session,
            workflow_service=workflow_service,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )

        #
        # Resume the existing job and session.
        #

        processed_job_id = worker.process_next()

        assert processed_job_id == job_id

        #
        # No report generation should occur.
        #

        assert report_calls == []

        #
        # Verify the original report was reused.
        #

        with Session() as db:

            repository = ReportRepository(
                db
            )

            persisted_report = repository.get_for_session(
                session_id
            )

            assert persisted_report is not None

            assert persisted_report.id == original_report_id

            assert persisted_report.title == (
                "Previously Persisted Report"
            )

            assert len(persisted_report.sections) == 1

            assert (
                persisted_report.sections[0].reviewed_claim_ids
                == []
            )

            report_count = db.execute(
                text("""
                    SELECT COUNT(*)
                    FROM dbo.research_reports
                    WHERE research_session_id = :session_id
                """),
                {
                    "session_id": session_id,
                },
            ).scalar_one()

            assert report_count == 1

        #
        # The real completion node should have
        # finished the research session.
        #

        with Session() as db:

            repository = ResearchSessionRepository(
                db
            )

            research_session = repository.get(
                session_id
            )

            assert research_session.status == "completed"

        #
        # The worker should have finalized the
        # original job without replacing its session.
        #

        completed_job = get_job_state(
            Session,
            job_id,
        )

        assert completed_job["status"] == "completed"

        assert completed_job["session_id"] == session_id

        assert completed_job["owner"] is None

    finally:

        cleanup_test_user_and_job(
            Session,
            user_id,
        )
