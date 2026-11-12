
from dataclasses import replace
from uuid import uuid4

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
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

from test_review_selection_fencing import (
    create_review_question,
    get_snapshot,
    set_session_status,
)

from test_review_completion_fencing import (
    acquire_lease,
)


def begin_reporting(
    session_id,
    lease,
):

    with SessionLocal() as db:

        ResearchSessionRepository(
            db
        ).begin_reporting_fenced(
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

        begin_reporting(
            session_id,
            lease,
        )

    except expected_exception:

        pass

    else:

        raise AssertionError(
            "Reporting transition was "
            "unexpectedly accepted."
        )

    after = {
        item: get_snapshot(item)
        for item in protected_sessions
    }

    assert after == before, (
        "Rejected reporting transition "
        "modified persisted research state."
    )


def main():

    print()
    print("REPORTING TRANSITION FENCING")
    print("============================")

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
                "reviewed",
            )

        #
        # A: Fully reviewed.
        #

        create_review_question(
            session_a,
            "reviewed",
        )

        create_review_question(
            session_a,
            "reviewed",
        )

        #
        # B: Incomplete review.
        #

        create_review_question(
            session_b,
            "reviewed",
        )

        create_review_question(
            session_b,
            "reviewing",
        )

        #
        # C: Fully reviewed, used for
        # lease-replacement testing.
        #

        create_review_question(
            session_c,
            "reviewed",
        )

        #
        # D: No research questions.
        #

        #
        # E: Unexpected question status.
        #

        create_review_question(
            session_e,
            "pending",
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
        # Successful transition.
        #

        begin_reporting(
            session_a,
            lease_a,
        )

        assert get_snapshot(
            session_a
        )[0] == "reporting"

        print(
            "TEST 1 - Reporting transition: PASSED"
        )

        #
        # Idempotent retry.
        #

        before = get_snapshot(
            session_a
        )

        begin_reporting(
            session_a,
            lease_a,
        )

        assert get_snapshot(
            session_a
        ) == before

        print(
            "TEST 2 - Idempotent retry: PASSED"
        )

        #
        # Unfinished review.
        #

        expect_rejection(
            session_b,
            lease_b,
            ValueError,
            [session_a, session_b],
        )

        print(
            "TEST 3 - Unfinished review rejected: PASSED"
        )

        #
        # No research questions.
        #

        expect_rejection(
            session_d,
            lease_d,
            ValueError,
            [session_d],
        )

        print(
            "TEST 4 - Empty research rejected: PASSED"
        )

        #
        # Unexpected question status.
        #

        expect_rejection(
            session_e,
            lease_e,
            ValueError,
            [session_e],
        )

        print(
            "TEST 5 - Unexpected question status rejected: PASSED"
        )

        #
        # Invalid starting status.
        #

        set_session_status(
            session_c,
            "researched",
        )

        expect_rejection(
            session_c,
            lease_c,
            ValueError,
            [session_c],
        )

        set_session_status(
            session_c,
            "reviewed",
        )

        print(
            "TEST 6 - Invalid starting status rejected: PASSED"
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
            "TEST 7 - Cross-session lease rejected: PASSED"
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
            "TEST 8 - Incorrect owner rejected: PASSED"
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
            "TEST 9 - Expired lease rejected: PASSED"
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
            "TEST 10 - Superseded lease rejected: PASSED"
        )

        #
        # Replacement worker succeeds.
        #

        begin_reporting(
            session_c,
            replacement_lease_c,
        )

        assert get_snapshot(
            session_c
        )[0] == "reporting"

        print(
            "TEST 11 - Replacement lease succeeds: PASSED"
        )

        #
        # Recovery from interrupted reporting.
        #

        before = get_snapshot(
            session_c
        )

        begin_reporting(
            session_c,
            replacement_lease_c,
        )

        assert get_snapshot(
            session_c
        ) == before

        print(
            "TEST 12 - Interrupted reporting recovery: PASSED"
        )

        #
        # Session isolation.
        #

        assert get_snapshot(
            session_b
        )[0] == "reviewed"

        assert get_snapshot(
            session_d
        )[0] == "reviewed"

        assert get_snapshot(
            session_e
        )[0] == "reviewed"

        print(
            "TEST 13 - Session isolation preserved: PASSED"
        )

        print()
        print("PASS")

    finally:

        for session_id in reversed(
            sessions
        ):

            delete_session(
                session_id
            )


if __name__ == "__main__":

    main()
