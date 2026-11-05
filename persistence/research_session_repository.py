from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import update

from domain.research_plan import ResearchPlan

from persistence.models import (
    ResearchQuestion,
    ResearchSession,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)

from sqlalchemy import text

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)

class RecoveryNotEligible(RuntimeError):
    """The session is no longer eligible for automatic recovery."""


class ResearchSessionRepository:

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def create(
        self,
        topic: str,
        scope: str | None = None,
    ) -> ResearchSession:

        topic = topic.strip()

        if not topic:
            raise ValueError(
                "A research topic is required."
            )

        if scope is not None:

            scope = scope.strip()

            if not scope:
                scope = None

        now = datetime.now(
            timezone.utc
        )

        research_session = ResearchSession(
            id=str(uuid4()),
            topic=topic,
            scope=scope,
            status="created",
            pause_requested=False,
            created_at=now,
            updated_at=now,
        )

        self.db.add(
            research_session
        )

        self.db.commit()

        return research_session

    def get(
        self,
        session_id: str,
    ) -> ResearchSession | None:

        return self.db.get(
            ResearchSession,
            session_id,
        )

    def set_status(
        self,
        session_id: str,
        status: str,
    ) -> None:

        research_session = self.db.get(
            ResearchSession,
            session_id,
        )

        if research_session is None:

            raise ValueError(
                "Research session not found: "
                f"{session_id}"
            )

        research_session.status = status

        research_session.updated_at = (
            datetime.now(
                timezone.utc
            )
        )

        self.db.commit()


    def set_scope(
        self,
        session_id: str,
        scope: str,
    ) -> ResearchSession:

        scope = scope.strip()

        if not scope:
            raise ValueError(
                "Research scope cannot be empty."
            )

        research_session = self.db.get(
            ResearchSession,
            session_id,
        )

        if research_session is None:
            raise ValueError(
                "Research session not found: "
                f"{session_id}"
            )

        research_session.scope = scope

        research_session.updated_at = (
            datetime.now(
                timezone.utc
            )
        )

        try:

            self.db.commit()

            self.db.refresh(
                research_session
            )

        except Exception:

            self.db.rollback()

            raise

        return research_session

  
    def request_pause(
        self,
        session_id: str,
    ) -> ResearchSession:

        research_session = self.db.get(
            ResearchSession,
            session_id,
        )

        if research_session is None:
            raise ValueError(
                "Research session not found: "
                f"{session_id}"
            )

        research_session.pause_requested = True

        research_session.updated_at = (
            datetime.now(
                timezone.utc
            )
        )

        try:

            self.db.commit()

            self.db.refresh(
                research_session
            )

        except Exception:

            self.db.rollback()

            raise

        return research_session


    def clear_pause_request(
        self,
        session_id: str,
    ) -> ResearchSession:

        research_session = self.db.get(
            ResearchSession,
            session_id,
        )

        if research_session is None:
            raise ValueError(
                "Research session not found: "
                f"{session_id}"
            )

        research_session.pause_requested = False

        research_session.updated_at = (
            datetime.now(
                timezone.utc
            )
        )

        try:

            self.db.commit()

            self.db.refresh(
                research_session
            )

        except Exception:

            self.db.rollback()

            raise

        return research_session


    def is_pause_requested(
        self,
        session_id: str,
    ) -> bool:

        research_session = self.db.get(
            ResearchSession,
            session_id,
        )

        if research_session is None:
            raise ValueError(
                "Research session not found: "
                f"{session_id}"
            )

        return (
            research_session.pause_requested
            is True
        )
    
    
    
    
    def save_plan(
        self,
        session_id: str,
        plan: ResearchPlan,
        lease: ExecutionLease,
    ) -> None:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            research_session = self.db.get(
                ResearchSession,
                session_id,
            )

            if research_session is None:

                raise ValueError(
                    "Research session not found: "
                    f"{session_id}"
                )

            existing_questions = (
                self.db.query(
                    ResearchQuestion
                )
                .filter(
                    ResearchQuestion.research_session_id
                    == session_id
                )
                .order_by(
                    ResearchQuestion.id
                )
                .all()
            )

            planned_questions = [
                question
                for question in existing_questions
                if question.category != "user_added"
            ]

            requested_questions = [
                (
                    question.category,
                    question.question,
                    question.rationale,
                )
                for question in plan.questions
            ]

            persisted_questions = [
                (
                    question.category,
                    question.question,
                    question.rationale,
                )
                for question in planned_questions
            ]

            #
            # An existing plan must be identical
            # to the requested plan.
            #

            if persisted_questions:

                if persisted_questions != requested_questions:

                    raise ValueError(
                        "Research plan differs from "
                        "the previously saved plan."
                    )

                if research_session.status == "planning":

                    raise ValueError(
                        "Research plan exists but "
                        "the session is still planning."
                    )

                self.db.commit()

                return

            #
            # A new research plan can only be
            # saved during the planning phase.
            #

            if research_session.status != "planning":

                raise ValueError(
                    "Research session is not ready "
                    "for research plan persistence."
                )

            if not requested_questions:

                raise ValueError(
                    "Research plan must contain "
                    "at least one question."
                )

            now = datetime.now(
                timezone.utc
            )

            for planned_question in plan.questions:

                question = ResearchQuestion(
                    research_session_id=session_id,
                    category=planned_question.category,
                    question=planned_question.question,
                    rationale=planned_question.rationale,
                    status="pending",
                    created_at=now,
                    updated_at=now,
                )

                self.db.add(
                    question
                )

            research_session.status = "planned"
            research_session.updated_at = now

            self.db.commit()

        except Exception:

            self.db.rollback()

            raise




    #
    # -------------------------------------------------
    # Research question lifecycle
    # -------------------------------------------------
    #

    def get_question(
        self,
        question_id: int,
    ) -> ResearchQuestion | None:

        return self.db.get(
            ResearchQuestion,
            question_id,
        )

    def set_question_status(
        self,
        question_id: int,
        status: str,
    ) -> None:

        question = self.db.get(
            ResearchQuestion,
            question_id,
        )

        if question is None:

            raise ValueError(
                "Research question not found: "
                f"{question_id}"
            )

        question.status = status

        question.updated_at = (
            datetime.now(
                timezone.utc
            )
        )

        self.db.commit()

    def get_next_pending_question(
        self,
        session_id: str,
    ) -> ResearchQuestion | None:

        return (
            self.db.query(
                ResearchQuestion
            )
            .filter(
                ResearchQuestion
                .research_session_id
                == session_id,

                ResearchQuestion.status
                == "pending",
            )
            .order_by(
                ResearchQuestion.id
            )
            .first()
        )

    def get_active_question(
        self,
        session_id: str,
    ) -> ResearchQuestion | None:

        return (
            self.db.query(
                ResearchQuestion
            )
            .filter(
                ResearchQuestion
                .research_session_id
                == session_id,

                ResearchQuestion.status
                == "researching",
            )
            .order_by(
                ResearchQuestion.id
            )
            .first()
        )

    #
    # -------------------------------------------------
    # Review question lifecycle
    # -------------------------------------------------
    #

    def get_next_question_for_review(
        self,
        session_id: str,
    ) -> ResearchQuestion | None:

        return (
            self.db.query(
                ResearchQuestion
            )
            .filter(
                ResearchQuestion
                .research_session_id
                == session_id,

                ResearchQuestion.status
                == "researched",
            )
            .order_by(
                ResearchQuestion.id
            )
            .first()
        )

    def get_active_review_question(
        self,
        session_id: str,
    ) -> ResearchQuestion | None:

        return (
            self.db.query(
                ResearchQuestion
            )
            .filter(
                ResearchQuestion
                .research_session_id
                == session_id,

                ResearchQuestion.status
                == "reviewing",
            )
            .order_by(
                ResearchQuestion.id
            )
            .first()
        )

    #
    # -------------------------------------------------
    # Workflow state queries
    # -------------------------------------------------
    #

    def has_unfinished_research_questions(
        self,
        session_id: str,
    ) -> bool:

        question = (
            self.db.query(
                ResearchQuestion
            )
            .filter(
                ResearchQuestion
                .research_session_id
                == session_id,

                ResearchQuestion.status.in_(
                    [
                        "pending",
                        "researching",
                    ]
                ),
            )
            .first()
        )

        return question is not None

    def has_unfinished_review_questions(
        self,
        session_id: str,
    ) -> bool:

        question = (
            self.db.query(
                ResearchQuestion
            )
            .filter(
                ResearchQuestion
                .research_session_id
                == session_id,

                ResearchQuestion.status.in_(
                    [
                        "researched",
                        "reviewing",
                    ]
                ),
            )
            .first()
        )

        return question is not None

    def get_questions(
        self,
        session_id: str,
    ) -> list[ResearchQuestion]:

        return (
            self.db.query(
                ResearchQuestion
            )
            .filter(
                ResearchQuestion.research_session_id
                == session_id
            )
            .order_by(
                ResearchQuestion.id
            )
            .all()
        )


    def find_question_by_text(
        self,
        session_id: str,
        question_text: str,
    ) -> ResearchQuestion | None:

        normalized_target = " ".join(
            question_text
            .strip()
            .casefold()
            .split()
        )

        if not normalized_target:
            return None

        questions = self.get_questions(
            session_id
        )

        matches = [
            question
            for question in questions
            if " ".join(
                question.question
                .strip()
                .casefold()
                .split()
            )
            == normalized_target
        ]

        if len(matches) > 1:
            raise ValueError(
                "Multiple research questions match "
                "the supplied question text."
            )

        if not matches:
            return None

        return matches[0]


    def add_question(
        self,
        session_id: str,
        question: str,
        category: str = "user_added",
        rationale: str = (
            "Added by the user during the research session."
        ),
    ) -> ResearchQuestion:

        question = question.strip()
        category = category.strip()
        rationale = rationale.strip()

        if not question:
            raise ValueError(
                "Research question cannot be empty."
            )

        if not category:
            raise ValueError(
                "Research question category "
                "cannot be empty."
            )

        if not rationale:
            raise ValueError(
                "Research question rationale "
                "cannot be empty."
            )

        research_session = self.get(
            session_id
        )

        if research_session is None:
            raise ValueError(
                "Research session not found."
            )

        now = datetime.now(
            timezone.utc
        )

        research_question = ResearchQuestion(
            research_session_id=session_id,
            category=category,
            question=question,
            rationale=rationale,
            status="pending",
            created_at=now,
            updated_at=now,
        )

        self.db.add(
            research_question
        )

        try:

            self.db.commit()

            self.db.refresh(
                research_question
            )

        except Exception:

            self.db.rollback()

            raise

        return research_question


    def set_status_pending_commit(
        self,
        session_id: str,
        status: str,
    ) -> None:

        research_session = self.db.get(
            ResearchSession,
            session_id,
        )

        if research_session is None:
            raise ValueError(
                "Research session not found: "
                f"{session_id}"
            )

        research_session.status = status

        research_session.updated_at = (
            datetime.now(
                timezone.utc
            )
        )


    def set_question_status_pending_commit(
        self,
        question_id: int,
        status: str,
    ) -> None:

        question = self.db.get(
            ResearchQuestion,
            question_id,
        )

        if question is None:
            raise ValueError(
                "Research question not found: "
                f"{question_id}"
            )

        question.status = status

        question.updated_at = (
            datetime.now(
                timezone.utc
            )
        )

    
    def set_question_status_fenced(
        self,
        session_id: str,
        question_id: int,
        status: str,
        lease: ExecutionLease,
    ) -> None:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            question = self.db.get(
                ResearchQuestion,
                question_id,
            )

            if (
                question is None
                or question.research_session_id
                != session_id
            ):

                raise ValueError(
                    "Research question does not belong "
                    "to the execution session."
                )

            if question.status == status:

                self.db.commit()

                return

            if (
                status == "researched"
                and question.status != "researching"
            ):

                raise ValueError(
                    "Only a researching question "
                    "can be marked as researched."
                )

            question.status = status

            self.db.flush()

            self.db.commit()

        except Exception:

            self.db.rollback()

            raise

    
    def select_question_fenced(
        self,
        session_id: str,
        lease: ExecutionLease,
    ) -> ResearchQuestion | None:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            research_session = self.get(
                session_id
            )

            if research_session is None:

                raise ValueError(
                    "Research session not found: "
                    f"{session_id}"
                )

            if research_session.status not in {
                "planned",
                "researching",
            }:

                raise ValueError(
                    "Cannot select a research question "
                    "while the research session is "
                    f"{research_session.status}."
                )

            #
            # Recover an existing active question
            # before selecting a new pending question.
            #

            question = self.get_active_question(
                session_id
            )

            if question is None:

                question = (
                    self.get_next_pending_question(
                        session_id
                    )
                )

                if question is not None:

                    if question.status != "pending":

                        raise ValueError(
                            "Selected question is not pending."
                        )

                    question.status = "researching"

            #
            # Once research work has started,
            # the parent session must reflect
            # the researching lifecycle state.
            #

            if question is not None:

                if research_session.status == "planned":

                    research_session.status = "researching"

            #
            # Persist the question selection and
            # parent lifecycle transition atomically.
            #

            self.db.commit()

            return question

        except Exception:

            self.db.rollback()

            raise


    
    def select_review_question_fenced(
        self,
        session_id: str,
        lease: ExecutionLease,
    ) -> ResearchQuestion | None:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            #
            # Fence the execution and lock the
            # research session for this transaction.
            #

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            #
            # Recover an existing review question
            # before selecting a new one.
            #

            question = (
                self.get_active_review_question(
                    session_id
                )
            )

            #
            # Otherwise select the next question
            # whose research has completed.
            #

            if question is None:

                question = (
                    self.get_next_question_for_review(
                        session_id
                    )
                )

                if question is not None:

                    question.status = "reviewing"

                    question.updated_at = (
                        datetime.now(
                            timezone.utc
                        )
                    )

            #
            # No question remains to review.
            #

            if question is None:

                self.db.commit()

                return None

            #
            # Set the session status within the
            # same transaction.
            #

            research_session = self.get(
                session_id
            )

            if research_session is None:

                raise ValueError(
                    "Research session not found: "
                    f"{session_id}"
                )

            if research_session.status != "reviewing":

                research_session.status = "reviewing"

                research_session.updated_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

            #
            # Commit question selection and
            # session status atomically.
            #

            self.db.flush()

            self.db.commit()

            self.db.refresh(
                question
            )

            return question

        except Exception:

            self.db.rollback()

            raise

    
    
        
    def complete_research_fenced(
        self,
        session_id: str,
        lease: ExecutionLease,
    ) -> None:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            research_session = self.db.get(
                ResearchSession,
                session_id,
            )

            if research_session is None:

                raise ValueError(
                    "Research session not found: "
                    f"{session_id}"
                )

            #
            # Idempotent recovery is allowed only
            # while the execution lease is valid.
            #

            if research_session.status == "researched":

                self.db.commit()

                return

            #
            # Research completion requires a
            # successfully persisted research plan.
            #

            if research_session.status not in {
                "planned",
                "researching",
            }:

                raise ValueError(
                    "Research session is not ready "
                    "for research completion."
                )

            #
            # At least one research question
            # must exist.
            #

            question_count = (
                self.db.query(
                    ResearchQuestion
                )
                .filter(
                    ResearchQuestion.research_session_id
                    == session_id
                )
                .count()
            )

            if question_count == 0:

                raise ValueError(
                    "Research cannot be completed "
                    "without research questions."
                )

            #
            # All questions must have completed
            # their research phase.
            #

            incomplete_count = (
                self.db.query(
                    ResearchQuestion
                )
                .filter(
                    ResearchQuestion.research_session_id
                    == session_id,
                    ~ResearchQuestion.status.in_(
                        {
                            "researched",
                            "reviewed",
                        }
                    ),
                )
                .count()
            )

            if incomplete_count > 0:

                raise ValueError(
                    "Research cannot be completed "
                    "while questions remain unfinished."
                )

            research_session.status = "researched"

            research_session.updated_at = (
                datetime.now(
                    timezone.utc
                )
            )

            self.db.flush()

            self.db.commit()

        except Exception:

            self.db.rollback()

            raise



    
    def complete_review_fenced(
        self,
        session_id: str,
        lease: ExecutionLease,
    ) -> None:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            research_session = self.db.get(
                ResearchSession,
                session_id,
            )

            if research_session is None:

                raise ValueError(
                    "Research session not found: "
                    f"{session_id}"
                )

            #
            # Allow a valid worker to retry a
            # previously completed transition.
            #

            if research_session.status == "reviewed":

                self.db.commit()

                return

            if research_session.status != "reviewing":

                raise ValueError(
                    "Research session is not ready "
                    "for review completion. "
                    f"Current status: {research_session.status}"
                )

            #
            # Require at least one research question.
            #

            question_count = self.db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM dbo.research_questions
                    WHERE research_session_id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            ).scalar_one()

            if question_count == 0:

                raise ValueError(
                    "Review cannot be completed "
                    "without research questions."
                )

            #
            # Every question must have completed
            # its review.
            #

            incomplete_count = self.db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM dbo.research_questions
                    WHERE research_session_id = :session_id
                    AND (
                        status IS NULL
                        OR status <> 'reviewed'
                    )
                    """
                ),
                {
                    "session_id": session_id,
                },
            ).scalar_one()

            if incomplete_count > 0:

                raise ValueError(
                    "Review cannot be completed "
                    "while questions remain unreviewed."
                )

            research_session.status = "reviewed"

            research_session.updated_at = (
                datetime.now(
                    timezone.utc
                )
            )

            self.db.flush()

            self.db.commit()

        except Exception:

            self.db.rollback()

            raise


        
    def begin_reporting_fenced(
        self,
        session_id: str,
        lease: ExecutionLease,
    ) -> None:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            research_session = self.db.get(
                ResearchSession,
                session_id,
            )

            if research_session is None:

                raise ValueError(
                    "Research session not found: "
                    f"{session_id}"
                )

            #
            # An interrupted reporting operation
            # can be resumed using a valid lease.
            #

            if research_session.status == "reporting":

                self.db.commit()

                return

            if research_session.status != "reviewed":

                raise ValueError(
                    "Research session is not ready "
                    "to begin reporting."
                )

            #
            # Require at least one research question.
            #

            question_count = self.db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM dbo.research_questions
                    WHERE research_session_id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            ).scalar_one()

            if question_count == 0:

                raise ValueError(
                    "Cannot begin reporting without "
                    "research questions."
                )

            #
            # Require every question to have
            # completed review.
            #

            incomplete_count = self.db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM dbo.research_questions
                    WHERE research_session_id = :session_id
                    AND (
                        status IS NULL
                        OR status <> 'reviewed'
                    )
                    """
                ),
                {
                    "session_id": session_id,
                },
            ).scalar_one()

            if incomplete_count > 0:

                raise ValueError(
                    "Cannot begin reporting while "
                    "questions remain unreviewed."
                )

            research_session.status = "reporting"

            research_session.updated_at = (
                datetime.now(
                    timezone.utc
                )
            )

            self.db.flush()

            self.db.commit()

        except Exception:

            self.db.rollback()

            raise


    
    def complete_report_fenced(
        self,
        session_id: str,
        lease: ExecutionLease,
    ) -> None:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            #
            # Validate execution ownership and hold
            # the session lock until commit.
            #

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            research_session = self.db.get(
                ResearchSession,
                session_id,
            )

            if research_session is None:

                raise ValueError(
                    "Research session not found: "
                    f"{session_id}"
                )

            #
            # Only reporting or completed sessions
            # may enter this operation.
            #

            if research_session.status not in (
                "reporting",
                "completed",
            ):

                raise ValueError(
                    "Research session is not ready "
                    "for report completion."
                )

            #
            # A durable report must exist even when
            # recovering an already completed session.
            #

            report_count = self.db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM dbo.research_reports
                    WHERE research_session_id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            ).scalar_one()

            if report_count == 0:

                raise RuntimeError(
                    "Cannot complete research session "
                    "because no persisted research "
                    "report exists."
                )

            #
            # Idempotent recovery.
            #

            if research_session.status == "completed":

                self.db.commit()

                return

            #
            # Final durable lifecycle transition.
            #

            research_session.status = "completed"

            research_session.updated_at = (
                datetime.now(
                    timezone.utc
                )
            )

            self.db.flush()

            self.db.commit()

        except Exception:

            self.db.rollback()

            raise

  
    def prepare_execution_fenced(
        self,
        session_id: str,
        lease: ExecutionLease,
        resume: bool,
    ) -> tuple[str, str | None]:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            research_session = self.db.get(
                ResearchSession,
                session_id,
                populate_existing=True,
            )

            if research_session is None:

                raise ValueError(
                    "Research session not found."
                )

            if (
                not resume
                and research_session.pause_requested is True
            ):

                raise RecoveryNotEligible(
                    "Initial execution rejected because "
                    "a pause has been requested for session "
                    f"{session_id}"
                )

            if research_session.status == "completed":

                raise ValueError(
                    "This research session has "
                    "already been completed."
                )

            if not resume:

                if research_session.status != "created":

                    raise ValueError(
                        "Research session cannot enter "
                        "planning from its current state."
                    )

                research_session.status = "planning"

                research_session.updated_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

                self.db.flush()

            topic = research_session.topic
            scope = research_session.scope

            self.db.commit()

            return topic, scope

        except Exception:

            self.db.rollback()

            raise


    def find_recovery_candidates(
        self,
        limit: int = 100,
    ) -> list[str]:

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 1000
        ):
            raise ValueError(
                "limit must be an integer from 1 to 1000"
            )

        statement = text(
            """
            SELECT TOP (:limit)
                id
            FROM dbo.research_sessions
            WHERE status IN (
                'planning',
                'planned',
                'researching',
                'reviewing',
                'reporting'
            )
            AND (
                pause_requested = 0
                OR pause_requested IS NULL
            )
            AND (
                execution_owner IS NULL
                OR execution_lease_expires_at IS NULL
                OR execution_lease_expires_at <= SYSUTCDATETIME()
            )
            ORDER BY
                updated_at ASC,
                id ASC
            """
        )

        rows = self.db.execute(
            statement,
            {
                "limit": limit,
            },
        ).all()

        return [
            str(row[0])
            for row in rows
        ]


    def find_recovery_candidates(self, limit: int = 100) -> list[str]:
        """Discover unpaused, unowned or expired in-flight sessions.

        Uses SQL Server time to match the execution-lease implementation.
        Discovery is advisory: resume() must still acquire the lease atomically.
        """
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 1000
        ):
            raise ValueError("limit must be an integer from 1 to 1000")

        statement = text("""
            SELECT TOP (:limit) id
            FROM dbo.research_sessions
            WHERE status IN (
                'planning', 'planned', 'researching', 'reviewing', 'reporting'
            )
              AND (pause_requested = 0 OR pause_requested IS NULL)
              AND (
                  execution_owner IS NULL
                  OR execution_lease_expires_at IS NULL
                  OR execution_lease_expires_at <= SYSUTCDATETIME()
              )
            ORDER BY updated_at ASC, id ASC
        """)

        return [
            str(row[0])
            for row in self.db.execute(statement, {"limit": limit}).all()
        ]

    
    def prepare_recovery_execution_fenced(
        self,
        session_id: str,
        lease: ExecutionLease,
    ) -> tuple[str, str | None]:
        """
        Atomically validate recovery eligibility and read session metadata.

        The execution lease must already have been acquired.

        This method deliberately does not clear pause_requested or
        change the session's workflow phase.
        """

        recoverable_statuses = {
            "planning",
            "planned",
            "researching",
            "researched",
            "reviewing",
            "reviewed",
            "reporting",
        }

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            # Validate the current owner and fencing version.
            #
            # fence() acquires an UPDLOCK/HOLDLOCK on the
            # research_sessions row. The lock remains held
            # until this transaction commits or rolls back.

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            # Read the current durable state while holding
            # the session-row lock.

            research_session = self.db.get(
                ResearchSession,
                session_id,
                populate_existing=True,
            )

            if research_session is None:

                raise RecoveryNotEligible(
                    "Research session no longer exists: "
                    f"{session_id}"
                )

            if research_session.pause_requested is True:

                raise RecoveryNotEligible(
                    "Automatic recovery rejected because "
                    "a pause has been requested for session "
                    f"{session_id}"
                )

            if research_session.status not in recoverable_statuses:

                raise RecoveryNotEligible(
                    "Automatic recovery rejected for session "
                    f"{session_id}. Current status: "
                    f"{research_session.status}"
                )

            topic = research_session.topic
            scope = research_session.scope

            # Commit releases the row lock. Subsequent
            # pause requests must be handled by the
            # graph's existing pause checkpoints.

            self.db.commit()

            return topic, scope

        except Exception:

            self.db.rollback()

            raise








