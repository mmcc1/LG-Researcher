
from unittest.mock import Mock

import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from domain.review import ResearchQuestionReview

from nodes.review_question import ReviewQuestionNode

from persistence.database import engine

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.review_repository import (
    ReviewRepository,
)


TEST_DATABASE = "LGResearcher_Test"


@pytest.fixture
def test_environment():

    test_url = engine.url.set(
        database=TEST_DATABASE
    )

    if test_url.database != TEST_DATABASE:

        raise RuntimeError(
            "Integration tests must use "
            "LGResearcher_Test."
        )

    test_engine = create_engine(
        test_url,
        echo=False,
    )

    Session = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    try:

        yield Session

    finally:

        test_engine.dispose()


def create_review_question(
    Session,
):

    with Session() as db:

        session_repository = (
            ResearchSessionRepository(db)
        )

        research_session = (
            session_repository.create(
                topic=(
                    "Aircraft wing drag and "
                    "material fatigue"
                ),
                scope=(
                    "Integration test of "
                    "insufficient evidence handling"
                ),
            )
        )

        session_id = research_session.id

        question = (
            session_repository.add_question(
                session_id=session_id,
                question=(
                    "How does drag influence "
                    "structural stress and "
                    "material fatigue?"
                ),
            )
        )

        question_id = question.id

        session_repository.set_question_status(
            question_id=question_id,
            status="researched",
        )

    return session_id, question_id


def delete_test_records(
    Session,
    session_id,
    question_id,
):

    with Session() as db:

        try:

            review_ids = db.execute(
                text(
                    """
                    SELECT id
                    FROM dbo.question_reviews
                    WHERE research_question_id = :question_id
                    """
                ),
                {
                    "question_id": question_id,
                },
            ).scalars().all()

            for review_id in review_ids:

                db.execute(
                    text(
                        """
                        DELETE FROM dbo.review_evidence_gaps
                        WHERE question_review_id = :review_id
                        """
                    ),
                    {
                        "review_id": review_id,
                    },
                )

                db.execute(
                    text(
                        """
                        DELETE FROM dbo.review_contradictions
                        WHERE question_review_id = :review_id
                        """
                    ),
                    {
                        "review_id": review_id,
                    },
                )

                db.execute(
                    text(
                        """
                        DELETE FROM dbo.question_reviews
                        WHERE id = :review_id
                        """
                    ),
                    {
                        "review_id": review_id,
                    },
                )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.research_questions
                    WHERE id = :question_id
                      AND research_session_id = :session_id
                    """
                ),
                {
                    "question_id": question_id,
                    "session_id": session_id,
                },
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.research_sessions
                    WHERE id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            db.commit()

        except Exception:

            db.rollback()
            raise


def test_no_findings_persisted_and_fenced(
    test_environment,
):

    Session = test_environment

    session_id = None
    question_id = None

    try:

        session_id, question_id = (
            create_review_question(
                Session
            )
        )

        with Session() as db:

            lease_repository = (
                ExecutionLeaseRepository(db)
            )

            lease = lease_repository.acquire(
                session_id=session_id,
                duration_seconds=120,
            )

        with Session() as db:

            session_repository = (
                ResearchSessionRepository(db)
            )

            selected_question = (
                session_repository
                .select_review_question_fenced(
                    session_id=session_id,
                    lease=lease,
                )
            )

            assert selected_question is not None
            assert selected_question.id == question_id
            assert selected_question.status == "reviewing"

        review_agent = Mock()
        context_builder = Mock()

        node = ReviewQuestionNode(
            session_factory=Session,
            review_agent=review_agent,
            context_builder=context_builder,
        )

        state = {
            "session_id": session_id,
            "current_review_question_id": question_id,
            "current_review_question": (
                "How does drag influence "
                "structural stress and "
                "material fatigue?"
            ),
        }

        config = {
            "configurable": {
                "execution_lease": lease,
            }
        }

        result = node(
            state=state,
            config=config,
        )

        assert result == {}

        review_agent.review.assert_not_called()
        context_builder.build.assert_not_called()

        with Session() as db:

            review_repository = (
                ReviewRepository(db)
            )

            persisted_review = (
                review_repository.get_for_question(
                    question_id
                )
            )

            assert persisted_review is not None

            assert persisted_review.answer == (
                "Insufficient evidence to answer "
                "the research question."
            )

            assert (
                persisted_review.overall_confidence
                == "low"
            )

            assert (
                persisted_review.sufficient_evidence
                is False
            )

            assert persisted_review.reviewed_claims == []
            assert persisted_review.contradictions == []

            assert persisted_review.evidence_gaps == [
                (
                    "No research findings were available "
                    "for this question."
                )
            ]

            original_review_id = persisted_review.id

            session_repository = (
                ResearchSessionRepository(db)
            )

            question = (
                session_repository.get_question(
                    question_id
                )
            )

            assert question.status == "reviewed"

        second_result = node(
            state=state,
            config=config,
        )

        assert second_result == {}

        review_agent.review.assert_not_called()

        with Session() as db:

            review_repository = (
                ReviewRepository(db)
            )

            persisted_review = (
                review_repository.get_for_question(
                    question_id
                )
            )

            assert persisted_review.id == original_review_id

            review_count = db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM dbo.question_reviews
                    WHERE research_question_id = :question_id
                    """
                ),
                {
                    "question_id": question_id,
                },
            ).scalar_one()

            assert review_count == 1

        with Session() as db:

            lease_repository = (
                ExecutionLeaseRepository(db)
            )

            released = lease_repository.release(
                lease
            )

            assert released is True

            replacement_lease = (
                lease_repository.acquire(
                    session_id=session_id,
                    duration_seconds=120,
                )
            )

            assert replacement_lease.version > lease.version

        with Session() as db:

            review_repository = (
                ReviewRepository(db)
            )

            with pytest.raises(
                ExecutionLeaseFenceRejected
            ):

                review_repository.save_review_fenced(
                    session_id=session_id,
                    question_id=question_id,
                    review=ResearchQuestionReview(
                        answer="Invalid stale review",
                        reviewed_claims=[],
                        contradictions=[],
                        evidence_gaps=[],
                        overall_confidence="low",
                        sufficient_evidence=False,
                    ),
                    valid_finding_ids=set(),
                    lease=lease,
                )

        with Session() as db:

            review_repository = (
                ReviewRepository(db)
            )

            persisted_review = (
                review_repository.get_for_question(
                    question_id
                )
            )

            assert persisted_review.id == original_review_id

            assert persisted_review.answer == (
                "Insufficient evidence to answer "
                "the research question."
            )

            lease_repository = (
                ExecutionLeaseRepository(db)
            )

            assert lease_repository.release(
                replacement_lease
            ) is True

    finally:

        if (
            session_id is not None
            and question_id is not None
        ):

            delete_test_records(
                Session=Session,
                session_id=session_id,
                question_id=question_id,
            )
