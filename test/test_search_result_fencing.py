from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import event, select, update

from domain.search import SearchResult

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import (
    ResearchQuestion,
    ResearchSession,
    SearchAttempt,
    WebSearchResult,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)

from persistence.search_repository import (
    SearchRepository,
)


def make_results() -> list[SearchResult]:

    return [
        SearchResult(
            url="https://example.com/architecture",
            title="Architecture",
            snippet="Technical architecture overview.",
            rank=1,
            query="system architecture",
            provider="test",
        ),
        SearchResult(
            url="https://example.com/security",
            title="Security",
            snippet="Security considerations.",
            rank=2,
            query="system security",
            provider="test",
        ),
    ]


def create_session() -> str:

    with SessionLocal() as db:

        research_session = ResearchSessionRepository(
            db
        ).create(
            topic=f"Disposable test {uuid4()}"
        )

        return research_session.id


def create_question(session_id: str) -> int:

    with SessionLocal() as db:

        now = datetime.now(timezone.utc)

        question = ResearchQuestion(
            research_session_id=session_id,
            category="Testing",
            question="What does the system do?",
            rationale="Verify search persistence.",
            status="researching",
            created_at=now,
            updated_at=now,
        )

        db.add(question)
        db.commit()

        return question.id


def create_running_attempt(
    session_id: str,
    question_id: int,
) -> int:

    with SessionLocal() as db:

        repository = SearchAttemptRepository(db)

        attempt = repository.create(
            session_id=session_id,
            question_id=question_id,
            purpose="initial",
        )

        repository.mark_running(
            attempt.id
        )

        return attempt.id


def get_snapshot(attempt_id: int):

    with SessionLocal() as db:

        attempt = db.get(
            SearchAttempt,
            attempt_id,
        )

        results = db.execute(
            select(
                WebSearchResult.id,
                WebSearchResult.query,
                WebSearchResult.provider,
                WebSearchResult.rank,
                WebSearchResult.url,
                WebSearchResult.title,
                WebSearchResult.snippet,
            )
            .where(
                WebSearchResult.search_attempt_id
                == attempt_id
            )
            .order_by(
                WebSearchResult.id
            )
        ).all()

        return (
            attempt.status,
            attempt.completed_at,
            tuple(tuple(row) for row in results),
        )


def save_results(
    session_id,
    question_id,
    attempt_id,
    lease,
    results=None,
):

    if results is None:
        results = make_results()

    with SessionLocal() as db:

        SearchRepository(db).save_attempt_results(
            session_id=session_id,
            question_id=question_id,
            attempt_id=attempt_id,
            results=results,
            lease=lease,
        )
        


def expect_rejection(
    session_id,
    question_id,
    attempt_id,
    lease,
    exception_type,
    results=None,
):

    before = get_snapshot(attempt_id)

    try:

        save_results(
            session_id=session_id,
            question_id=question_id,
            attempt_id=attempt_id,
            lease=lease,
            results=results,
        )

    except exception_type:

        pass

    else:

        raise AssertionError(
            "Search results were unexpectedly accepted."
        )

    assert get_snapshot(attempt_id) == before, (
        "Rejected operation changed the attempt."
    )


def expire_lease(session_id):

    with SessionLocal() as db:

        db.execute(
            update(ResearchSession)
            .where(
                ResearchSession.id == session_id
            )
            .values(
                execution_lease_expires_at=datetime(
                    2000, 1, 1
                )
            )
        )

        db.commit()


def delete_session(session_id):

    with SessionLocal() as db:

        attempt_ids = select(
            SearchAttempt.id
        ).where(
            SearchAttempt.research_session_id
            == session_id
        )

        db.query(
            WebSearchResult
        ).filter(
            WebSearchResult.search_attempt_id.in_(
                attempt_ids
            )
        ).delete(
            synchronize_session=False
        )

        db.query(
            SearchAttempt
        ).filter(
            SearchAttempt.research_session_id
            == session_id
        ).delete(
            synchronize_session=False
        )

        db.query(
            ResearchQuestion
        ).filter(
            ResearchQuestion.research_session_id
            == session_id
        ).delete(
            synchronize_session=False
        )

        db.query(
            ResearchSession
        ).filter(
            ResearchSession.id
            == session_id
        ).delete(
            synchronize_session=False
        )

        db.commit()

    print(
        f"Disposable session removed: {session_id}"
    )


def main():

    print()
    print("SEARCH RESULT FENCING")
    print("=====================")

    session_a = create_session()
    session_b = create_session()

    try:

        question_a = create_question(
            session_a
        )

        question_b = create_question(
            session_b
        )

        attempt_a = create_running_attempt(
            session_a,
            question_a,
        )

        attempt_b = create_running_attempt(
            session_b,
            question_b,
        )

        with SessionLocal() as db:

            lease_a = ExecutionLeaseRepository(
                db
            ).acquire(session_a)

            lease_b = ExecutionLeaseRepository(
                db
            ).acquire(session_b)

        save_results(
            session_a,
            question_a,
            attempt_a,
            lease_a,
        )

        status, completed_at, results = (
            get_snapshot(attempt_a)
        )

        assert status == "completed"
        assert completed_at is not None
        assert len(results) == 2

        print(
            "TEST 1 - Valid results committed: PASSED"
        )

        original = get_snapshot(
            attempt_a
        )

        save_results(
            session_a,
            question_a,
            attempt_a,
            lease_a,
        )

        assert get_snapshot(attempt_a) == original

        print(
            "TEST 2 - Identical retry unchanged: PASSED"
        )

        different_results = make_results()

        different_results[0] = (
            different_results[0].model_copy(
                update={
                    "title": "Changed title"
                }
            )
        )

        expect_rejection(
            session_a,
            question_a,
            attempt_a,
            lease_a,
            ValueError,
            different_results,
        )

        print(
            "TEST 3 - Changed retry rejected: PASSED"
        )

        incorrect_owner = replace(
            lease_b,
            owner=str(uuid4()),
        )

        expect_rejection(
            session_b,
            question_b,
            attempt_b,
            incorrect_owner,
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 4 - Incorrect owner rejected: PASSED"
        )

        expire_lease(
            session_b
        )

        expect_rejection(
            session_b,
            question_b,
            attempt_b,
            lease_b,
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 5 - Expired lease rejected: PASSED"
        )

        with SessionLocal() as db:

            replacement_lease_b = (
                ExecutionLeaseRepository(db).acquire(
                    session_b
                )
            )

        expect_rejection(
            session_b,
            question_b,
            attempt_b,
            lease_b,
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 6 - Superseded lease rejected: PASSED"
        )

        expect_rejection(
            session_b,
            question_b,
            attempt_b,
            lease_a,
            ValueError,
        )

        print(
            "TEST 7 - Cross-session lease rejected: PASSED"
        )

        expect_rejection(
            session_b,
            question_a,
            attempt_b,
            replacement_lease_b,
            ValueError,
        )

        print(
            "TEST 8 - Cross-session question rejected: PASSED"
        )

        expect_rejection(
            session_b,
            question_b,
            attempt_a,
            replacement_lease_b,
            ValueError,
        )

        print(
            "TEST 9 - Cross-session attempt rejected: PASSED"
        )

        before = get_snapshot(
            attempt_b
        )

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

                    SearchRepository(
                        db
                    ).save_attempt_results(
                        session_id=session_b,
                        question_id=question_b,
                        attempt_id=attempt_b,
                        results=make_results(),
                        lease=replacement_lease_b,
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

        assert get_snapshot(attempt_b) == before

        print(
            "TEST 10 - Failed transaction rolled back: PASSED"
        )

        save_results(
            session_b,
            question_b,
            attempt_b,
            replacement_lease_b,
        )

        status, completed_at, results = (
            get_snapshot(attempt_b)
        )

        assert status == "completed"
        assert completed_at is not None
        assert len(results) == 2

        print(
            "TEST 11 - Valid write after rollback: PASSED"
        )

        print()
        print("PASS")

    finally:

        delete_session(session_b)
        delete_session(session_a)


if __name__ == "__main__":

    main()
