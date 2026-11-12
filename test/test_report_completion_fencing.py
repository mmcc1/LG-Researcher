
from dataclasses import replace
from uuid import uuid4

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from test_search_result_fencing import (
    create_session,
    delete_session,
    expire_lease,
)

from test_review_completion_fencing import (
    acquire_lease,
)

from test_review_selection_fencing import (
    get_snapshot,
    set_session_status,
)

from test_report_persistence_fencing import (
    delete_report,
    make_report,
    persist_report,
)


def complete_report(
    session_id,
    lease,
):

    with SessionLocal() as db:

        ResearchSessionRepository(
            db
        ).complete_report_fenced(
            session_id=session_id,
            lease=lease,
        )


def expect_rejection(
    session_id,
    lease,
    expected_exception,
    protected_sessions,
):

    before = {
        item: get_snapshot(item)
        for item in protected_sessions
    }

    try:

        complete_report(
            session_id,
            lease,
        )

    except expected_exception:

        pass

    else:

        raise AssertionError(
            "Report completion was "
            "unexpectedly accepted."
        )

    after = {
        item: get_snapshot(item)
        for item in protected_sessions
    }

    assert after == before, (
        "Rejected report completion "
        "modified persisted research state."
    )


def main():

    print()
    print("REPORT COMPLETION FENCING")
    print("=========================")

    sessions = []

    try:

        session_a = create_session()
        sessions.append(session_a)

        session_b = create_session()
        sessions.append(session_b)

        session_c = create_session()
        sessions.append(session_c)

        session_d = create_session()
        sessions.append(session_d)

        session_e = create_session()
        sessions.append(session_e)

        for session_id in sessions:

            set_session_status(
                session_id,
                "reporting",
            )

        lease_a = acquire_lease(
            session_a
        )

        lease_b = acquire_lease(
            session_b
        )

        lease_c = acquire_lease(
            session_c
        )

        lease_d = acquire_lease(
            session_d
        )

        lease_e = acquire_lease(
            session_e
        )

        #
        # Persist reports for sessions that
        # will be eligible for completion.
        #

        persist_report(
            session_a,
            make_report(),
            lease_a,
        )

        persist_report(
            session_c,
            make_report(),
            lease_c,
        )

        persist_report(
            session_d,
            make_report(),
            lease_d,
        )

        persist_report(
            session_e,
            make_report(),
            lease_e,
        )

        #
        # Successful completion.
        #

        complete_report(
            session_a,
            lease_a,
        )

        assert get_snapshot(
            session_a
        )[0] == "completed"

        print(
            "TEST 1 - Report completion persisted: PASSED"
        )

        #
        # Idempotent completion.
        #

        before = get_snapshot(
            session_a
        )

        complete_report(
            session_a,
            lease_a,
        )

        assert get_snapshot(
            session_a
        ) == before

        print(
            "TEST 2 - Idempotent completion: PASSED"
        )

        #
        # Missing durable report.
        #

        expect_rejection(
            session_b,
            lease_b,
            RuntimeError,
            [session_a, session_b],
        )

        print(
            "TEST 3 - Missing report rejected: PASSED"
        )

        #
        # Invalid lifecycle state.
        #

        set_session_status(
            session_c,
            "reviewed",
        )

        expect_rejection(
            session_c,
            lease_c,
            ValueError,
            [session_c],
        )

        set_session_status(
            session_c,
            "reporting",
        )

        print(
            "TEST 4 - Invalid lifecycle state rejected: PASSED"
        )

        #
        # Cross-session lease.
        #

        expect_rejection(
            session_c,
            lease_a,
            ValueError,
            [session_a, session_c],
        )

        print(
            "TEST 5 - Cross-session lease rejected: PASSED"
        )

        #
        # Incorrect owner.
        #

        invalid_lease = replace(
            lease_c,
            owner=str(uuid4()),
        )

        expect_rejection(
            session_c,
            invalid_lease,
            ExecutionLeaseFenceRejected,
            [session_c],
        )

        print(
            "TEST 6 - Incorrect owner rejected: PASSED"
        )

        #
        # Expired lease.
        #

        expire_lease(
            session_c
        )

        expect_rejection(
            session_c,
            lease_c,
            ExecutionLeaseFenceRejected,
            [session_c],
        )

        print(
            "TEST 7 - Expired lease rejected: PASSED"
        )

        #
        # Superseded lease.
        #

        replacement_lease_c = (
            acquire_lease(
                session_c
            )
        )

        assert (
            replacement_lease_c.version
            > lease_c.version
        )

        expect_rejection(
            session_c,
            lease_c,
            ExecutionLeaseFenceRejected,
            [session_c],
        )

        print(
            "TEST 8 - Superseded lease rejected: PASSED"
        )

        #
        # Replacement worker completes.
        #

        complete_report(
            session_c,
            replacement_lease_c,
        )

        assert get_snapshot(
            session_c
        )[0] == "completed"

        print(
            "TEST 9 - Replacement worker succeeds: PASSED"
        )

        #
        # A superseded worker must also be
        # rejected after completion.
        #

        expect_rejection(
            session_c,
            lease_c,
            ExecutionLeaseFenceRejected,
            [session_c],
        )

        print(
            "TEST 10 - Stale completion retry rejected: PASSED"
        )

        #
        # Completed session with missing report.
        #
        # Simulate an inconsistent durable state.
        #

        set_session_status(
            session_b,
            "completed",
        )

        expect_rejection(
            session_b,
            lease_b,
            RuntimeError,
            [session_b],
        )

        print(
            "TEST 11 - Inconsistent completion rejected: PASSED"
        )

        #
        # Session isolation.
        #

        assert get_snapshot(
            session_a
        )[0] == "completed"

        assert get_snapshot(
            session_c
        )[0] == "completed"

        assert get_snapshot(
            session_d
        )[0] == "reporting"

        assert get_snapshot(
            session_e
        )[0] == "reporting"

        print(
            "TEST 12 - Session isolation preserved: PASSED"
        )

        print()
        print("PASS")

    finally:

        for session_id in reversed(
            sessions
        ):

            delete_report(
                session_id
            )

            delete_session(
                session_id
            )


if __name__ == "__main__":

    main()
