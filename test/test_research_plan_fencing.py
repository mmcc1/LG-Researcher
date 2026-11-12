
from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from sqlalchemy import event, select, update

from persistence.database import SessionLocal

from domain.research_plan import (
    ResearchPlan,
    ResearchQuestionPlan,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import (
    ResearchQuestion,
    ResearchSession,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


def make_plan() -> ResearchPlan:

    return ResearchPlan(
        topic="Disposable research topic",
        questions=[
            ResearchQuestionPlan(
                category="Architecture",
                question="How does the system operate?",
                rationale="Establish the architecture.",
            ),
            ResearchQuestionPlan(
                category="Security",
                question="What security risks exist?",
                rationale="Identify security risks.",
            ),
        ],
    )


def create_session() -> str:

    with SessionLocal() as db:

        repository = ResearchSessionRepository(
            db
        )

        research_session = repository.create(
            topic=f"Disposable test {uuid4()}"
        )

        session_id = research_session.id

        repository.set_status(
            session_id,
            "planning",
        )

        return session_id


def get_snapshot(session_id: str):

    with SessionLocal() as db:

        research_session = db.get(
            ResearchSession,
            session_id,
        )

        questions = db.execute(
            select(
                ResearchQuestion.category,
                ResearchQuestion.question,
                ResearchQuestion.rationale,
                ResearchQuestion.status,
            ).where(
                ResearchQuestion.research_session_id
                == session_id
            ).order_by(
                ResearchQuestion.id
            )
        ).all()

        return (
            research_session.status,
            tuple(tuple(row) for row in questions),
        )


def save_plan(session_id, lease):

    with SessionLocal() as db:

        ResearchSessionRepository(db).save_plan(
            session_id=session_id,
            plan=make_plan(),
            lease=lease,
        )


def expect_rejection(
    session_id,
    lease,
    exception_type,
):

    before = get_snapshot(session_id)

    with SessionLocal() as db:

        try:

            ResearchSessionRepository(db).save_plan(
                session_id=session_id,
                plan=make_plan(),
                lease=lease,
            )

        except exception_type:

            pass

        else:

            raise AssertionError(
                "Plan was unexpectedly saved."
            )

    after = get_snapshot(session_id)

    assert after == before, (
        "Rejected write changed the research session."
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
            ResearchSession.id == session_id
        ).delete(
            synchronize_session=False
        )

        db.commit()

    print(
        f"Disposable session removed: {session_id}"
    )


def main():

    print()
    print("RESEARCH PLAN FENCING")
    print("=====================")

    session_a = create_session()
    session_b = create_session()

    try:

        with SessionLocal() as db:

            lease_a = ExecutionLeaseRepository(
                db
            ).acquire(session_a)

            lease_b = ExecutionLeaseRepository(
                db
            ).acquire(session_b)

        # Valid plan persistence.

        save_plan(
            session_a,
            lease_a,
        )

        status, questions = get_snapshot(
            session_a
        )

        assert status == "planned"
        assert len(questions) == 2

        assert questions[0] == (
            "Architecture",
            "How does the system operate?",
            "Establish the architecture.",
            "pending",
        )

        assert questions[1] == (
            "Security",
            "What security risks exist?",
            "Identify security risks.",
            "pending",
        )

        print(
            "TEST 1 - Valid plan committed: PASSED"
        )

        # Incorrect execution owner.

        incorrect_owner = replace(
            lease_b,
            owner=str(uuid4()),
        )

        expect_rejection(
            session_b,
            incorrect_owner,
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 2 - Incorrect owner rejected: PASSED"
        )

        # Expired execution lease.

        expire_lease(
            session_b
        )

        expect_rejection(
            session_b,
            lease_b,
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 3 - Expired lease rejected: PASSED"
        )

        # Superseded execution lease.

        with SessionLocal() as db:

            replacement_lease_b = (
                ExecutionLeaseRepository(db).acquire(
                    session_b
                )
            )

        assert (
            replacement_lease_b.version
            > lease_b.version
        )

        expect_rejection(
            session_b,
            lease_b,
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 4 - Superseded lease rejected: PASSED"
        )

        # Valid lease for the wrong session.

        expect_rejection(
            session_b,
            lease_a,
            ValueError,
        )

        print(
            "TEST 5 - Cross-session lease rejected: PASSED"
        )

        # Force failure after SQLAlchemy flushes
        # the question inserts.

        before = get_snapshot(
            session_b
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

                    ResearchSessionRepository(
                        db
                    ).save_plan(
                        session_id=session_b,
                        plan=make_plan(),
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

        assert get_snapshot(session_b) == before

        print(
            "TEST 6 - Failed transaction rolled back: PASSED"
        )

        # Verify recovery after rollback.

        save_plan(
            session_b,
            replacement_lease_b,
        )

        status, questions = get_snapshot(
            session_b
        )

        assert status == "planned"
        assert len(questions) == 2

        print(
            "TEST 7 - Valid write after rollback: PASSED"
        )

        print()
        print("PASS")

    finally:

        delete_session(session_b)
        delete_session(session_a)


if __name__ == "__main__":

    main()
