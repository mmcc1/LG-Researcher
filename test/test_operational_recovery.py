from collections import Counter
from uuid import uuid4

from sqlalchemy import text

from application.research_recovery_service import ResearchRecoveryService
from application.research_workflow_service import ResearchWorkflowService
from persistence.database import SessionLocal
from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseUnavailable,
)
from persistence.research_session_repository import ResearchSessionRepository
from test_research_graph_integration import (
    FakeSearchProvider,
    FakeDocumentRetriever,
    cleanup_graph_test_session,
)
from test_review_graph_integration import cleanup_reviews, rows, status
from test_report_graph_integration import make_graph, cleanup_report
from test_report_graph_pause_resume import report_counts
from test_workflow_controller_integration import assert_lease_released
from test_workflow_controller_pause_resume import SessionBindingGraph
from test_workflow_controller_crash_recovery import (
    ControllerCrashOnceModel,
    InjectedControllerReportCrash,
)


def make_candidate(status_value, paused=False):
    """Create a disposable session containing no research child rows."""
    with SessionLocal() as db:
        repository = ResearchSessionRepository(db)
        session = repository.create(
            topic=f"Operational recovery eligibility {uuid4()}",
            scope="Disposable candidate selection test",
        )
        session_id = session.id
        session.status = status_value
        session.pause_requested = paused
        db.commit()
        return session_id


def delete_empty_session(session_id):
    with SessionLocal() as db:
        db.execute(
            text("DELETE FROM dbo.research_sessions WHERE id = :session_id"),
            {"session_id": session_id},
        )
        db.commit()



class RacingController:
    """
    Simulate another worker winning ownership
    after recovery candidate discovery.

    The recovery coordinator should classify
    the resulting lease contention as "skipped".
    """

    def __init__(self):

        self.attempts = []

    def recover(
        self,
        session_id,
    ):

        self.attempts.append(
            session_id
        )

        with SessionLocal() as db:

            lease = ExecutionLeaseRepository(
                db
            ).acquire(
                session_id
            )

        try:

            raise ExecutionLeaseUnavailable(
                "Competing controller owns the lease"
            )

        finally:

            with SessionLocal() as db:

                assert ExecutionLeaseRepository(
                    db
                ).release(
                    lease
                )


def main():
    disposable_ids = []
    session_id = None
    held_lease = None

    print("OPERATIONAL RECOVERY INTEGRATION")
    print("================================")

    try:
        model = ControllerCrashOnceModel()
        search = FakeSearchProvider()
        retriever = FakeDocumentRetriever()
        graph = SessionBindingGraph(
            graph=make_graph(model, search, retriever),
            model=model,
        )
        workflow = ResearchWorkflowService(
            graph=graph,
            session_factory=SessionLocal,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )
        recovery = ResearchRecoveryService(workflow, SessionLocal)
        print("TEST 1 - Production recovery coordinator prepared: PASSED")

        # Candidate eligibility is checked independently from the real graph.
        eligible = make_candidate("planning")
        active = make_candidate("researching")
        paused = make_candidate("reporting", paused=True)
        completed = make_candidate("completed")
        created = make_candidate("created")
        researched = make_candidate("researched")
        reviewed = make_candidate("reviewed")
        disposable_ids.extend([
            eligible, active, paused, completed, created, researched, reviewed,
        ])

        with SessionLocal() as db:
            held_lease = ExecutionLeaseRepository(db).acquire(active)

        candidates = recovery.find_candidates(limit=1000)
        assert eligible in candidates
        print("TEST 2 - Unowned in-flight session discovered: PASSED")

        assert active not in candidates
        print("TEST 3 - Active lease excluded: PASSED")

        assert paused not in candidates
        print("TEST 4 - User-paused session excluded: PASSED")

        assert completed not in candidates
        assert created not in candidates
        assert researched not in candidates
        assert reviewed not in candidates
        print("TEST 5 - Completed and phase-boundary sessions excluded: PASSED")

        with SessionLocal() as db:
            assert ExecutionLeaseRepository(db).release(held_lease)
        held_lease = None

        with SessionLocal() as db:
            held_lease = ExecutionLeaseRepository(db).acquire(active)
            db.execute(
                text("""
                    UPDATE dbo.research_sessions
                    SET execution_lease_expires_at = DATEADD(second, -10, SYSUTCDATETIME())
                    WHERE id = :session_id
                """),
                {"session_id": active},
            )
            db.commit()

        assert active in recovery.find_candidates(limit=1000)
        print("TEST 6 - Expired lease discovered: PASSED")
        held_lease = None  # Deliberately expired; deletion handles the test row.

        for invalid_limit in (0, -1, 1001, True, 1.5):
            try:
                recovery.find_candidates(limit=invalid_limit)
            except ValueError:
                pass
            else:
                raise AssertionError(f"Invalid limit accepted: {invalid_limit!r}")
        print("TEST 7 - Candidate limit validation: PASSED")

        # Remove synthetic candidates before running a broad recovery scan.
        for candidate_id in disposable_ids:
            delete_empty_session(candidate_id)
        disposable_ids.clear()

        try:
            workflow.start(
                topic="Operational recovery of interrupted report generation",
                scope="Deterministic persisted research evidence",
            )
        except InjectedControllerReportCrash:
            pass
        else:
            raise AssertionError("Expected injected report-generation interruption")

        session_id = model.session_id
        assert session_id is not None
        assert status(session_id) == "reporting"
        assert_lease_released(session_id)
        assert report_counts(session_id)["reports"] == 0
        print("TEST 8 - Interrupted reporting session persisted and unowned: PASSED")

        assert session_id in recovery.find_candidates(limit=1000)
        print("TEST 9 - Interrupted real workflow selected for recovery: PASSED")

        # Crash occurred before the base ReportModel populated this ID.
        # Restore it from durable reviewed claims, as in controller crash tests.
        claim_rows = rows(
            """
            SELECT c.id
            FROM dbo.reviewed_claims c
            JOIN dbo.question_reviews qr ON qr.id = c.question_review_id
            JOIN dbo.research_questions q ON q.id = qr.research_question_id
            WHERE q.research_session_id = :session_id
            """,
            session_id=session_id,
        )
        assert len(claim_rows) == 1
        model.reviewed_claim_id = claim_rows[0].id

        previous_calls = Counter(model.calls)
        previous_search_count = len(search.calls)
        previous_retrieval_count = len(retriever.calls)

        # Restrict the recovery run to the test session even if unrelated
        # abandoned sessions exist in the developer's database.
        recovery.find_candidates = lambda limit=100: [session_id]
        outcomes = recovery.recover()
        assert len(outcomes) == 1
        assert outcomes[0].session_id == session_id
        assert outcomes[0].status == "resumed", outcomes
        assert status(session_id) == "completed"
        print("TEST 10 - Coordinator resumed workflow to completion: PASSED")

        assert report_counts(session_id) == {
            "reports": 1,
            "sections": 1,
            "references": 1,
            "limitations": 1,
        }
        assert_lease_released(session_id)
        print("TEST 11 - Single valid report hierarchy and lease release: PASSED")

        assert len(search.calls) == previous_search_count
        assert len(retriever.calls) == previous_retrieval_count
        for name, count in previous_calls.items():
            assert model.calls[name] == count
        assert model.calls["ResearchReport"] == 1
        assert session_id not in ResearchRecoveryService(workflow, SessionLocal).find_candidates(limit=1000)
        print("TEST 12 - No repeated research/review and no completed rediscovery: PASSED")

        # A separate synthetic in-flight session is used for a controlled race.
        racing_id = make_candidate("planning")
        disposable_ids.append(racing_id)
        racing_controller = RacingController()
        racing_recovery = ResearchRecoveryService(racing_controller, SessionLocal)
        racing_recovery.find_candidates = lambda limit=100: [racing_id]
        race_outcomes = racing_recovery.recover()
        assert len(race_outcomes) == 1
        assert race_outcomes[0].status == "skipped"
        assert racing_controller.attempts == [racing_id]
        print("TEST 13 - Competing acquisition classified as skipped: PASSED")

        print("\nPASS")

    finally:
        if held_lease is not None:
            try:
                with SessionLocal() as db:
                    ExecutionLeaseRepository(db).release(held_lease)
            except Exception:
                pass

        for candidate_id in disposable_ids:
            delete_empty_session(candidate_id)

        if session_id is None and "model" in locals():
            session_id = model.session_id

        if session_id is not None:
            try:
                cleanup_report(session_id)
            finally:
                try:
                    cleanup_reviews(session_id)
                finally:
                    cleanup_graph_test_session(session_id)


if __name__ == "__main__":
    main()
