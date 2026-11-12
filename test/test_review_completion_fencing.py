
from dataclasses import replace
from uuid import uuid4

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
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


def acquire_lease(
    session_id: str,
):

    with SessionLocal() as db:

        return ExecutionLeaseRepository(
            db
        ).acquire(
            session_id
        )


def complete_review(
    session_id: str,
    lease,
):

    with SessionLocal() as db:

        ResearchSessionRepository(
            db
        ).complete_review_fenced(
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

        complete_review(
            session_id,
            lease,
        )

    except expected_exception:

        pass

    else:

        raise AssertionError(
            "Review completion was "
            "unexpectedly accepted."
        )

    after = {
        item: get_snapshot(item)
        for item in protected_sessions
    }

    assert after == before, (
        "Rejected completion modified "
        "persisted research state."
    )


def main():

    print()
    print("REVIEW COMPLETION FENCING")
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

        set_session_status(
            session_a,
            "researched",
        )

        set_session_status(
            session_b,
            "researched",
        )

        set_session_status(
            session_c,
            "researched",
        )

        set_session_status(
            session_d,
            "researched",
        )

        create_review_question(
            session_a,
            "reviewed",
        )

        create_review_question(
            session_a,
            "reviewed",
        )

        create_review_question(
            session_b,
            "researched",
        )

        create_review_question(
            session_b,
            "reviewing",
        )

        create_review_question(
            session_c,
            "reviewed",
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

        # Successful completion.

        complete_review(
            session_a,
            lease_a,
        )

        assert get_snapshot(
            session_a
        )[0] == "reviewed"

        print(
            "TEST 1 - Review completion: PASSED"
        )

        # Idempotent retry.

        before = get_snapshot(
            session_a
        )

        complete_review(
            session_a,
            lease_a,
        )

        assert get_snapshot(
            session_a
        ) == before

        print(
            "TEST 2 - Idempotent retry: PASSED"
        )

        # Unreviewed questions.

        expect_rejection(
            session_b,
            lease_b,
            ValueError,
            [session_a, session_b],
        )

        print(
            "TEST 3 - Unreviewed questions rejected: PASSED"
        )

        # No research questions.

        expect_rejection(
            session_d,
            lease_d,
            ValueError,
            [session_d],
        )

        print(
            "TEST 4 - Empty review rejected: PASSED"
        )

        # Incorrect starting status.

        set_session_status(
            session_c,
            "planning",
        )

        expect_rejection(
            session_c,
            lease_c,
            ValueError,
            [session_c],
        )

        set_session_status(
            session_c,
            "researched",
        )

        print(
            "TEST 5 - Invalid starting status rejected: PASSED"
        )

        # Cross-session lease.

        expect_rejection(
            session_c,
            lease_a,
            ValueError,
            [session_a, session_c],
        )

        print(
            "TEST 6 - Cross-session lease rejected: PASSED"
        )

        # Incorrect lease owner.

        invalid_lease = replace(
            lease_c,
            owner=str(uuid4()),
        )

        expect_rejection(
            session_c,
            invalid_lease,
            Exception,
            [session_c],
        )

        print(
            "TEST 7 - Incorrect owner rejected: PASSED"
        )

        # Expired lease.

        expire_lease(
            session_c
        )

        expect_rejection(
            session_c,
            lease_c,
            Exception,
            [session_c],
        )

        print(
            "TEST 8 - Expired lease rejected: PASSED"
        )

        # Superseded lease.

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
            Exception,
            [session_c],
        )

        print(
            "TEST 9 - Superseded lease rejected: PASSED"
        )

        # Recovery using replacement lease.

        complete_review(
            session_c,
            replacement_lease_c,
        )

        assert get_snapshot(
            session_c
        )[0] == "reviewed"

        print(
            "TEST 10 - Replacement lease succeeds: PASSED"
        )

        # Confirm other sessions were not
        # modified by recovery.

        assert get_snapshot(
            session_b
        )[0] == "researched"

        assert get_snapshot(
            session_d
        )[0] == "researched"

        print(
            "TEST 11 - Session isolation: PASSED"
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
