
from dataclasses import replace
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy import event, select

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import (
    ResearchQuestion,
    SearchAttempt,
    WebSearchResult,
)

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)

from test_search_result_fencing import (
    create_session,
    create_question,
    delete_session,
    expire_lease,
    make_results,
)


def set_question_pending(
    question_id: int,
) -> None:

    with SessionLocal() as db:

        question = db.get(
            ResearchQuestion,
            question_id,
        )

        assert question is not None

        question.status = "pending"

        db.commit()


def resolve(
    session_id,
    question_id,
    lease,
):

    with SessionLocal() as db:

        return SearchAttemptRepository(
            db
        ).resolve_search_attempt_fenced(
            session_id=session_id,
            question_id=question_id,
            lease=lease,
        )


def get_attempts(
    question_id,
):

    with SessionLocal() as db:

        rows = db.execute(
            select(
                SearchAttempt.id,
                SearchAttempt.research_session_id,
                SearchAttempt.purpose,
                SearchAttempt.status,
                SearchAttempt.instructions,
                SearchAttempt.completed_at,
            )
            .where(
                SearchAttempt.research_question_id
                == question_id
            )
            .order_by(
                SearchAttempt.id
            )
        ).all()

        return tuple(
            tuple(row)
            for row in rows
        )


def set_attempt_status(
    attempt_id,
    status,
):

    with SessionLocal() as db:

        attempt = db.get(
            SearchAttempt,
            attempt_id,
        )

        assert attempt is not None

        attempt.status = status

        db.commit()


def create_attempt(
    session_id,
    question_id,
    status="pending",
):

    with SessionLocal() as db:

        attempt = SearchAttemptRepository(
            db
        ).create(
            session_id=session_id,
            question_id=question_id,
            purpose="initial",
        )

        attempt_id = attempt.id

        if status != "pending":

            attempt.status = status

            db.commit()

        return attempt_id



def add_legacy_results(
    session_id,
    question_id,
):

    results = make_results()

    with SessionLocal() as db:

        for result in results:

            db.add(
                WebSearchResult(
                    research_session_id=session_id,
                    research_question_id=question_id,
                    search_attempt_id=None,
                    query=result.query,
                    provider=result.provider,
                    rank=result.rank,
                    url=result.url,
                    title=result.title,
                    snippet=result.snippet,
                    created_at=datetime.now(
                        timezone.utc
                    ),
                )
            )

        db.commit()



def expect_rejection(
    operation,
    question_ids,
    exception_type,
):

    before = {
        question_id: get_attempts(
            question_id
        )
        for question_id in question_ids
    }

    try:

        operation()

    except exception_type:

        pass

    else:

        raise AssertionError(
            "Search attempt operation "
            "was unexpectedly accepted."
        )

    after = {
        question_id: get_attempts(
            question_id
        )
        for question_id in question_ids
    }

    assert after == before, (
        "Rejected operation changed "
        "search attempt persistence."
    )


def cleanup_legacy_results(
    session_id,
):

    with SessionLocal() as db:

        db.query(
            WebSearchResult
        ).filter(
            WebSearchResult.research_session_id
            == session_id
        ).delete(
            synchronize_session=False
        )

        db.commit()


def main():

    print()
    print("SEARCH ATTEMPT RESOLUTION FENCING")
    print("=================================")

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

        question_a = create_question(
            session_a
        )

        question_b = create_question(
            session_b
        )

        question_c = create_question(
            session_c
        )

        question_d = create_question(
            session_d
        )

        for question_id in (
            question_a,
            question_b,
            question_c,
            question_d,
        ):

            set_question_pending(
                question_id
            )

        with SessionLocal() as db:

            lease_a = ExecutionLeaseRepository(
                db
            ).acquire(
                session_a
            )

            lease_b = ExecutionLeaseRepository(
                db
            ).acquire(
                session_b
            )

            lease_c = ExecutionLeaseRepository(
                db
            ).acquire(
                session_c
            )

            lease_d = ExecutionLeaseRepository(
                db
            ).acquire(
                session_d
            )

        # A new question requires an initial attempt.

        required, attempt_a = resolve(
            session_a,
            question_a,
            lease_a,
        )

        assert required is True
        assert attempt_a is not None

        attempts = get_attempts(
            question_a
        )

        assert len(attempts) == 1
        assert attempts[0][0] == attempt_a
        assert attempts[0][2] == "initial"
        assert attempts[0][3] == "running"

        print(
            "TEST 1 - Initial attempt created: PASSED"
        )

        # Repeated resolution resumes the same attempt.

        required, resumed_id = resolve(
            session_a,
            question_a,
            lease_a,
        )

        assert required is True
        assert resumed_id == attempt_a
        assert len(get_attempts(question_a)) == 1

        print(
            "TEST 2 - Running attempt resumed: PASSED"
        )

        # Existing pending attempt transitions to running.

        pending_id = create_attempt(
            session_b,
            question_b,
        )

        required, resumed_id = resolve(
            session_b,
            question_b,
            lease_b,
        )

        assert required is True
        assert resumed_id == pending_id
        assert get_attempts(question_b)[0][3] == "running"

        print(
            "TEST 3 - Pending attempt resumed: PASSED"
        )

        # Completed history prevents another initial attempt.

        set_attempt_status(
            attempt_a,
            "completed",
        )

        required, resolved_id = resolve(
            session_a,
            question_a,
            lease_a,
        )

        assert required is False
        assert resolved_id is None
        assert len(get_attempts(question_a)) == 1

        print(
            "TEST 4 - Completed history skips search: PASSED"
        )

        # Legacy search results also prevent a new attempt.

        add_legacy_results(
            session_c,
            question_c,
        )

        required, resolved_id = resolve(
            session_c,
            question_c,
            lease_c,
        )

        assert required is False
        assert resolved_id is None
        assert get_attempts(question_c) == ()

        print(
            "TEST 5 - Legacy results skip search: PASSED"
        )

        # Invalid owner cannot resolve a question.

        invalid_lease = replace(
            lease_d,
            owner=str(uuid4()),
        )

        expect_rejection(
            lambda: resolve(
                session_d,
                question_d,
                invalid_lease,
            ),
            [question_d],
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 6 - Invalid owner rejected: PASSED"
        )

        # Expired lease cannot create an attempt.

        expire_lease(
            session_d
        )

        expect_rejection(
            lambda: resolve(
                session_d,
                question_d,
                lease_d,
            ),
            [question_d],
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 7 - Expired lease rejected: PASSED"
        )

        # Acquire a replacement lease.

        with SessionLocal() as db:

            replacement_lease_d = (
                ExecutionLeaseRepository(db)
                .acquire(
                    session_d
                )
            )

        expect_rejection(
            lambda: resolve(
                session_d,
                question_d,
                lease_d,
            ),
            [question_d],
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 8 - Superseded lease rejected: PASSED"
        )

        # A lease for another session is invalid.

        expect_rejection(
            lambda: resolve(
                session_d,
                question_d,
                lease_a,
            ),
            [question_d],
            ValueError,
        )

        print(
            "TEST 9 - Cross-session lease rejected: PASSED"
        )

        # A valid lease cannot resolve another
        # session's question.

        expect_rejection(
            lambda: resolve(
                session_d,
                question_a,
                replacement_lease_d,
            ),
            [question_a, question_d],
            ValueError,
        )

        print(
            "TEST 10 - Cross-session question rejected: PASSED"
        )

        # Failure after an insert flush must roll
        # back the attempt creation.

        with SessionLocal() as db:

            def fail_after_flush(
                session,
                flush_context,
            ):

                raise RuntimeError(
                    "Simulated transaction failure."
                )

            event.listen(
                db,
                "after_flush",
                fail_after_flush,
            )

            try:

                try:

                    SearchAttemptRepository(
                        db
                    ).resolve_search_attempt_fenced(
                        session_id=session_d,
                        question_id=question_d,
                        lease=replacement_lease_d,
                    )

                except RuntimeError as exc:

                    assert str(exc) == (
                        "Simulated transaction failure."
                    )

                else:

                    raise AssertionError(
                        "Expected transaction failure."
                    )

            finally:

                event.remove(
                    db,
                    "after_flush",
                    fail_after_flush,
                )

        assert get_attempts(
            question_d
        ) == ()

        print(
            "TEST 11 - Creation rollback: PASSED"
        )

        # A valid retry succeeds after rollback.

        required, recovered_id = resolve(
            session_d,
            question_d,
            replacement_lease_d,
        )

        assert required is True
        assert recovered_id is not None
        assert get_attempts(question_d)[0][3] == "running"

        print(
            "TEST 12 - Recovery after rollback: PASSED"
        )

        # Verify the other sessions remain unchanged.

        assert len(get_attempts(question_a)) == 1
        assert len(get_attempts(question_b)) == 1
        assert get_attempts(question_c) == ()

        print(
            "TEST 13 - Session isolation preserved: PASSED"
        )

        print()
        print("PASS")

    finally:

        for session_id in reversed(
            sessions
        ):

            cleanup_legacy_results(
                session_id
            )

            delete_session(
                session_id
            )


if __name__ == "__main__":

    main()
