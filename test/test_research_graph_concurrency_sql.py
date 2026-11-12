
from threading import Event, Thread, current_thread

from sqlalchemy import text

from agents.report_agent import ReportAgent

from application.research_job_worker import (
    ResearchJobWorker,
)

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from domain.review import ResearchQuestionReview

from domain.report import (
    ResearchReport,
    ReportSection,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
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

from test_research_graph_recovery_sql import (
    test_environment,
    create_test_user,
    create_failed_recovery_job,
    create_test_graph,
    get_job_state,
    cleanup_test_user_and_job,
)


def create_review():

    return ResearchQuestionReview(
        answer=(
            "Insufficient evidence to answer "
            "the research question."
        ),
        reviewed_claims=[],
        contradictions=[],
        evidence_gaps=[
            "No research findings were available.",
        ],
        overall_confidence="low",
        sufficient_evidence=False,
    )


def create_report(
    title,
):

    return ResearchReport(
        title=title,
        executive_summary=(
            "The available evidence is insufficient."
        ),
        sections=[
            ReportSection(
                heading="Evidence Assessment",
                content=(
                    "No supporting research findings "
                    "were available."
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
    )


def prepare_reporting_session(
    Session,
    session_id,
    question_ids,
):

    with Session() as db:

        lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    try:

        for question_id in question_ids:

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
                    review=create_review(),
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

    finally:

        with Session() as db:

            released = ExecutionLeaseRepository(
                db
            ).release(
                lease
            )

            assert released is True


def expire_current_session_lease(
    Session,
    session_id,
):

    with Session() as db:

        row = db.execute(
            text("""
                SELECT
                    execution_owner,
                    execution_lease_version
                FROM dbo.research_sessions
                WHERE id = :session_id
            """),
            {
                "session_id": session_id,
            },
        ).one()

        owner = row[0]
        version = row[1]

        assert owner is not None

        result = db.execute(
            text("""
                UPDATE dbo.research_sessions
                SET execution_lease_expires_at =
                    DATEADD(
                        second,
                        -1,
                        SYSUTCDATETIME()
                    )
                WHERE id = :session_id
                  AND execution_owner = :owner
                  AND execution_lease_version = :version
                  AND execution_lease_expires_at >
                      SYSUTCDATETIME()
            """),
            {
                "session_id": session_id,
                "owner": owner,
                "version": version,
            },
        )

        assert result.rowcount == 1

        db.commit()

        return owner, version


def get_session_state(
    Session,
    session_id,
):

    with Session() as db:

        row = db.execute(
            text("""
                SELECT
                    status,
                    execution_owner,
                    execution_lease_version
                FROM dbo.research_sessions
                WHERE id = :session_id
            """),
            {
                "session_id": session_id,
            },
        ).one()

        return {
            "status": row[0],
            "owner": row[1],
            "version": row[2],
        }


def get_report_count(
    Session,
    session_id,
):

    with Session() as db:

        return db.execute(
            text("""
                SELECT COUNT(*)
                FROM dbo.research_reports
                WHERE research_session_id = :session_id
            """),
            {
                "session_id": session_id,
            },
        ).scalar_one()


def test_concurrent_graph_execution_rejects_stale_owner(
    test_environment,
    monkeypatch,
):

    Session, session_ids = test_environment

    user_id = create_test_user(
        Session
    )

    original_entered = Event()
    release_original = Event()

    original_result = {
        "completed": False,
        "error": None,
    }

    report_calls = []

    original_thread = None

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

        prepare_reporting_session(
            Session,
            session_id,
            (
                first_question_id,
                second_question_id,
            ),
        )

        initial_state = get_session_state(
            Session,
            session_id,
        )

        assert initial_state["status"] == "reporting"
        assert initial_state["owner"] is None

        assert get_report_count(
            Session,
            session_id,
        ) == 0

        graph = create_test_graph(
            Session,
            monkeypatch,
            [],
        )

        def generate_report(
            self,
            topic,
            reviewed_evidence,
        ):

            thread_name = current_thread().name

            report_calls.append(
                thread_name
            )

            if thread_name == "original-graph-execution":

                original_entered.set()

                released = release_original.wait(
                    timeout=15
                )

                if not released:

                    raise TimeoutError(
                        "Original execution was not released."
                    )

                return create_report(
                    "Stale Execution Report"
                )

            return create_report(
                "Replacement Execution Report"
            )

        monkeypatch.setattr(
            ReportAgent,
            "generate",
            generate_report,
        )

        original_workflow = ResearchWorkflowService(
            graph=graph,
            session_factory=Session,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )

        replacement_workflow = ResearchWorkflowService(
            graph=graph,
            session_factory=Session,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )

        replacement_worker = ResearchJobWorker(
            session_factory=Session,
            workflow_service=replacement_workflow,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )

        def execute_original():

            try:

                original_workflow.execute_existing(
                    session_id=session_id,
                )

                original_result["completed"] = True

            except Exception as exc:

                original_result["error"] = exc

        original_thread = Thread(
            target=execute_original,
            name="original-graph-execution",
            daemon=True,
        )

        original_thread.start()

        #
        # Wait until the original execution has
        # acquired its lease and entered the
        # Report Agent.
        #

        assert original_entered.wait(
            timeout=10
        ), (
            "Original execution did not reach "
            "report generation."
        )

        active_state = get_session_state(
            Session,
            session_id,
        )

        assert active_state["status"] == "reporting"
        assert active_state["owner"] is not None

        #
        # Expire the original execution's lease
        # while it is blocked inside the agent.
        #

        old_owner, old_version = (
            expire_current_session_lease(
                Session,
                session_id,
            )
        )

        #
        # The replacement worker claims the
        # queued job and resumes the same session.
        #
        # The original agent remains blocked.
        #

        processed_job_id = (
            replacement_worker.process_next()
        )

        assert processed_job_id == job_id

        replacement_state = get_session_state(
            Session,
            session_id,
        )

        assert replacement_state["status"] == "completed"

        assert replacement_state["owner"] is None

        assert replacement_state["version"] > old_version

        completed_job = get_job_state(
            Session,
            job_id,
        )

        assert completed_job["status"] == "completed"
        assert completed_job["session_id"] == session_id

        #
        # Capture the replacement's committed
        # report before releasing the old worker.
        #

        with Session() as db:

            repository = ReportRepository(
                db
            )

            replacement_report = (
                repository.get_for_session(
                    session_id
                )
            )

            assert replacement_report is not None

            replacement_report_id = (
                replacement_report.id
            )

            assert replacement_report.title == (
                "Replacement Execution Report"
            )

        assert get_report_count(
            Session,
            session_id,
        ) == 1

        #
        # Resume the original execution.
        #
        # Its session lease has been superseded.
        # It must not complete successfully.
        #

        release_original.set()

        original_thread.join(
            timeout=10
        )

        assert not original_thread.is_alive(), (
            "Original execution did not terminate."
        )

        assert original_result["completed"] is False

        assert original_result["error"] is not None

        #
        # Verify the stale execution did not
        # overwrite or duplicate the report.
        #

        with Session() as db:

            repository = ReportRepository(
                db
            )

            persisted_report = (
                repository.get_for_session(
                    session_id
                )
            )

            assert persisted_report is not None

            assert persisted_report.id == (
                replacement_report_id
            )

            assert persisted_report.title == (
                "Replacement Execution Report"
            )

        assert get_report_count(
            Session,
            session_id,
        ) == 1

        final_state = get_session_state(
            Session,
            session_id,
        )

        assert final_state["status"] == "completed"
        assert final_state["owner"] is None

        final_job = get_job_state(
            Session,
            job_id,
        )

        assert final_job["status"] == "completed"

        assert report_calls.count(
            "original-graph-execution"
        ) == 1

        assert len(report_calls) == 2

    finally:

        release_original.set()

        if original_thread is not None:

            original_thread.join(
                timeout=10
            )

        cleanup_test_user_and_job(
            Session,
            user_id,
        )
