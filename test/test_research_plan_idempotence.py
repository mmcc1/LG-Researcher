
from uuid import uuid4

from sqlalchemy import select

from persistence.database import SessionLocal

from domain.research_plan import (
    ResearchPlan,
    ResearchQuestionPlan,
)

from persistence.execution_lease_repository import (
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
        topic="Idempotence test",
        questions=[
            ResearchQuestionPlan(
                category="Architecture",
                question="How does the system operate?",
                rationale="Understand the architecture.",
            ),
            ResearchQuestionPlan(
                category="Security",
                question="What are the security risks?",
                rationale="Identify potential risks.",
            ),
        ],
    )


def create_session():

    with SessionLocal() as db:

        repository = ResearchSessionRepository(db)

        research_session = repository.create(
            topic=f"Disposable test {uuid4()}"
        )

        session_id = research_session.id

        repository.set_status(
            session_id,
            "planning",
        )

        lease = ExecutionLeaseRepository(
            db
        ).acquire(session_id)

        return session_id, lease


def get_questions(session_id):

    with SessionLocal() as db:

        return db.execute(
            select(
                ResearchQuestion.id,
                ResearchQuestion.category,
                ResearchQuestion.question,
                ResearchQuestion.rationale,
                ResearchQuestion.status,
            )
            .where(
                ResearchQuestion.research_session_id
                == session_id
            )
            .order_by(
                ResearchQuestion.id
            )
        ).all()


def get_status(session_id):

    with SessionLocal() as db:

        return db.get(
            ResearchSession,
            session_id,
        ).status


def save_plan(session_id, lease, plan):

    with SessionLocal() as db:

        ResearchSessionRepository(db).save_plan(
            session_id=session_id,
            plan=plan,
            lease=lease,
        )


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
    print("RESEARCH PLAN IDEMPOTENCE")
    print("=========================")

    session_id, lease = create_session()

    try:

        plan = make_plan()

        save_plan(
            session_id,
            lease,
            plan,
        )

        original_questions = get_questions(
            session_id
        )

        assert len(original_questions) == 2
        assert get_status(session_id) == "planned"

        print(
            "TEST 1 - Initial plan saved: PASSED"
        )

        save_plan(
            session_id,
            lease,
            plan,
        )

        assert (
            get_questions(session_id)
            == original_questions
        )

        print(
            "TEST 2 - Repeated plan unchanged: PASSED"
        )

        different_plan = ResearchPlan(
            topic=plan.topic,
            questions=[
                ResearchQuestionPlan(
                    category="Different",
                    question="A different question?",
                    rationale="A different rationale.",
                )
            ],
        )

        try:

            save_plan(
                session_id,
                lease,
                different_plan,
            )

        except ValueError:

            pass

        else:

            raise AssertionError(
                "Different plan was accepted."
            )

        assert (
            get_questions(session_id)
            == original_questions
        )

        print(
            "TEST 3 - Different plan rejected: PASSED"
        )

        with SessionLocal() as db:

            ResearchSessionRepository(db).add_question(
                session_id=session_id,
                question="User supplied question?",
            )

        questions_with_user = get_questions(
            session_id
        )

        assert len(questions_with_user) == 3

        save_plan(
            session_id,
            lease,
            plan,
        )

        assert (
            get_questions(session_id)
            == questions_with_user
        )

        print(
            "TEST 4 - User question preserved: PASSED"
        )

        with SessionLocal() as db:

            question = db.get(
                ResearchQuestion,
                original_questions[0].id,
            )

            question.status = "researched"

            db.commit()

        progressed_questions = get_questions(
            session_id
        )

        save_plan(
            session_id,
            lease,
            plan,
        )

        assert (
            get_questions(session_id)
            == progressed_questions
        )

        print(
            "TEST 5 - Question progress preserved: PASSED"
        )

        print()
        print("PASS")

    finally:

        delete_session(session_id)


if __name__ == "__main__":

    main()
