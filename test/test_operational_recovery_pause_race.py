from application.research_recovery_service import (
    ResearchRecoveryService,
)

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from persistence.database import SessionLocal

from persistence.research_session_repository import (
    ResearchSessionRepository,
    RecoveryNotEligible,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
)

from test_research_graph_integration import (
    cleanup_graph_test_session,
)


class RecordingGraph:
    """Record production-controller graph invocations."""

    def __init__(self):

        self.calls = []

    def invoke(
        self,
        initial_state,
        config=None,
    ):

        self.calls.append(
            {
                "state": dict(initial_state),
                "config": config,
            }
        )

        return {
            "session_id": initial_state["session_id"],
            "pause_requested": False,
        }


def create_session(
    status="reporting",
):

    with SessionLocal() as db:

        repository = ResearchSessionRepository(
            db
        )

        session = repository.create(
            topic="Disposable recovery pause race test",
            scope="Execution eligibility fencing",
        )

        session_id = session.id

        repository.set_status(
            session_id,
            status,
        )

        return session_id


def snapshot(
    session_id,
):

    with SessionLocal() as db:

        session = ResearchSessionRepository(
            db
        ).get(
            session_id
        )

        assert session is not None

        return {
            "status": session.status,
            "paused": bool(
                session.pause_requested
            ),
            "owner": session.execution_owner,
            "expiry": session.execution_lease_expires_at,
            "version": int(
                session.execution_lease_version
            ),
        }


def request_pause(
    session_id,
):

    with SessionLocal() as db:

        ResearchSessionRepository(
            db
        ).request_pause(
            session_id
        )


def clear_pause(
    session_id,
):

    with SessionLocal() as db:

        ResearchSessionRepository(
            db
        ).clear_pause_request(
            session_id
        )


def make_services():

    graph = RecordingGraph()

    workflow = ResearchWorkflowService(
        graph=graph,
        session_factory=SessionLocal,
        lease_duration_seconds=30,
        heartbeat_interval_seconds=5.0,
    )

    recovery = ResearchRecoveryService(
        workflow_service=workflow,
        session_factory=SessionLocal,
    )

    return graph, workflow, recovery


def assert_lease_released(
    session_id,
):

    state = snapshot(
        session_id
    )

    assert state["owner"] is None
    assert state["expiry"] is None


def main():

    session_ids = []

    print(
        "OPERATIONAL RECOVERY - PAUSE REQUEST RACE"
    )

    print(
        "========================================="
    )

    try:

        graph, workflow, recovery = make_services()

        print(
            "TEST 1 - Production recovery services prepared: PASSED"
        )

        session_id = create_session(
            status="reporting"
        )

        session_ids.append(
            session_id
        )

        candidates = recovery.find_candidates(
            limit=1000
        )

        assert session_id in candidates

        print(
            "TEST 2 - Unpaused session discovered for recovery: PASSED"
        )

        # Simulate the user requesting a pause
        # after the recovery coordinator has
        # already discovered the candidate.

        request_pause(
            session_id
        )

        assert snapshot(
            session_id
        )["paused"]

        print(
            "TEST 3 - Pause requested after candidate discovery: PASSED"
        )

        # Force the coordinator to process its
        # previously discovered candidate.
        #
        # This reproduces the stale-candidate race.

        recovery.find_candidates = (
            lambda limit=100: [session_id]
        )

        outcomes = recovery.recover()

        assert len(outcomes) == 1
        assert outcomes[0].session_id == session_id
        assert outcomes[0].status == "skipped"

        print(
            "TEST 4 - Stale candidate rejected by fenced eligibility: PASSED"
        )

        # The controller must not invoke the graph
        # after rejecting recovery eligibility.

        assert len(graph.calls) == 0

        print(
            "TEST 5 - Rejected recovery performed no graph work: PASSED"
        )

        # Although the controller acquired a lease,
        # it must release it when the eligibility
        # check raises RecoveryNotEligible.

        assert_lease_released(
            session_id
        )

        assert snapshot(
            session_id
        )["paused"]

        print(
            "TEST 6 - Lease released and pause request preserved: PASSED"
        )

        # Explicit resume remains a separate
        # operation. It must not use the automatic
        # recovery eligibility restriction.
        #
        # The recording graph does not change
        # durable workflow status.

        explicit_result = workflow.resume(
            session_id
        )

        assert (
            explicit_result.session_id
            == session_id
        )

        assert len(graph.calls) == 1

        assert (
            graph.calls[0]["state"]["resume"]
            is True
        )

        assert_lease_released(
            session_id
        )

        print(
            "TEST 7 - Explicit resume remains available: PASSED"
        )

        # Clear the user pause request.
        #
        # The session is still in reporting status
        # because RecordingGraph does not perform
        # durable graph transitions.

        clear_pause(
            session_id
        )

        assert not snapshot(
            session_id
        )["paused"]

        result = workflow.recover(
            session_id
        )

        assert result.session_id == session_id

        assert len(graph.calls) == 2

        assert (
            graph.calls[1]["state"]["resume"]
            is True
        )

        assert_lease_released(
            session_id
        )

        print(
            "TEST 8 - Eligible session recovered through production controller: PASSED"
        )

        # Completed sessions must not be recovered.

        with SessionLocal() as db:

            ResearchSessionRepository(
                db
            ).set_status(
                session_id,
                "completed",
            )

        calls_before = len(
            graph.calls
        )

        try:

            workflow.recover(
                session_id
            )

        except RecoveryNotEligible:

            pass

        else:

            raise AssertionError(
                "Completed session was not rejected"
            )

        assert len(graph.calls) == calls_before

        assert_lease_released(
            session_id
        )

        print(
            "TEST 9 - Completed session rejected before graph invocation: PASSED"
        )

        # A phase-boundary session must not be
        # advanced automatically.

        boundary_id = create_session(
            status="reviewed"
        )

        session_ids.append(
            boundary_id
        )

        try:

            workflow.recover(
                boundary_id
            )

        except RecoveryNotEligible:

            pass

        else:

            raise AssertionError(
                "Phase-boundary session was not rejected"
            )

        assert len(graph.calls) == calls_before

        assert_lease_released(
            boundary_id
        )

        print(
            "TEST 10 - Intentional phase boundary excluded: PASSED"
        )

        # An active execution lease must still
        # prevent a second controller from
        # acquiring ownership.

        active_id = create_session(
            status="reporting"
        )

        session_ids.append(
            active_id
        )

        with SessionLocal() as db:

            active_lease = ExecutionLeaseRepository(
                db
            ).acquire(
                active_id,
                duration_seconds=30,
            )

        try:

            from persistence.execution_lease_repository import (
                ExecutionLeaseUnavailable,
            )

            try:

                workflow.recover(
                    active_id
                )

            except ExecutionLeaseUnavailable:

                pass

            else:

                raise AssertionError(
                    "Active lease did not prevent recovery"
                )

            assert len(graph.calls) == calls_before

            print(
                "TEST 11 - Active execution lease prevents competing recovery: PASSED"
            )

        finally:

            with SessionLocal() as db:

                released = ExecutionLeaseRepository(
                    db
                ).release(
                    active_lease
                )

                assert released

        # Verify that the candidate query itself
        # excludes the now-completed and
        # phase-boundary sessions.

        fresh_recovery = ResearchRecoveryService(
            workflow_service=workflow,
            session_factory=SessionLocal,
        )

        fresh_candidates = fresh_recovery.find_candidates(
            limit=1000
        )

        assert session_id not in fresh_candidates
        assert boundary_id not in fresh_candidates

        print(
            "TEST 12 - Completed and phase-boundary sessions excluded from discovery: PASSED"
        )

        print(
            "\nPASS"
        )

    finally:

        for session_id in reversed(
            session_ids
        ):

            cleanup_graph_test_session(
                session_id
            )

            print(
                "Disposable session removed: "
                f"{session_id}"
            )


if __name__ == "__main__":

    main()
