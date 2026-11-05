from datetime import datetime, timezone

from persistence.models import (
    SearchAttempt,
)

from sqlalchemy import text

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)

from persistence.models import ResearchQuestion

from persistence.search_repository import (
    SearchRepository,
)


class SearchAttemptRepository:

    VALID_PURPOSES = {
        "initial",
        "deeper_research",
        "counter_evidence",
    }

    VALID_STATUSES = {
        "pending",
        "running",
        "completed",
    }

    def __init__(
        self,
        db,
    ):
        self.db = db

    def add(
        self,
        session_id: str,
        question_id: int,
        purpose: str,
        instructions: str | None = None,
    ) -> SearchAttempt:

        purpose = purpose.strip()

        if purpose not in self.VALID_PURPOSES:
            raise ValueError(
                f"Unsupported search attempt "
                f"purpose '{purpose}'."
            )

        if instructions is not None:
            instructions = instructions.strip()

            if not instructions:
                instructions = None

        existing = (
            self.db.query(SearchAttempt)
            .filter(
                SearchAttempt.research_question_id
                == question_id,
                SearchAttempt.purpose
                == purpose,
                SearchAttempt.status.in_(
                    {
                        "pending",
                        "running",
                    }
                ),
            )
            .first()
        )

        if existing is not None:
            raise ValueError(
                "An outstanding search attempt "
                f"already exists for question "
                f"{question_id} with purpose "
                f"'{purpose}'."
            )

        now = datetime.now(
            timezone.utc
        )

        attempt = SearchAttempt(
            research_session_id=session_id,
            research_question_id=question_id,
            purpose=purpose,
            status="pending",
            instructions=instructions,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )

        self.db.add(
            attempt
        )

        #
        # We need the database-generated ID while
        # remaining inside the caller's transaction.
        #

        self.db.flush()

        return attempt


    def create(
        self,
        session_id: str,
        question_id: int,
        purpose: str,
        instructions: str | None = None,
    ) -> SearchAttempt:

        try:

            attempt = self.add(
                session_id=session_id,
                question_id=question_id,
                purpose=purpose,
                instructions=instructions,
            )

            self.db.commit()

            self.db.refresh(
                attempt
            )

            return attempt

        except Exception:

            self.db.rollback()

            raise

    def get(
        self,
        attempt_id: int,
    ) -> SearchAttempt | None:

        return (
            self.db.query(SearchAttempt)
            .filter(
                SearchAttempt.id
                == attempt_id
            )
            .first()
        )

    def get_for_question(
        self,
        question_id: int,
    ) -> list[SearchAttempt]:

        return (
            self.db.query(SearchAttempt)
            .filter(
                SearchAttempt.research_question_id
                == question_id
            )
            .order_by(
                SearchAttempt.id
            )
            .all()
        )


    def has_attempts_for_question(
        self,
        question_id: int,
    ) -> bool:

        return (
            self.db.query(SearchAttempt)
            .filter(
                SearchAttempt.research_question_id
                == question_id
            )
            .first()
            is not None
        )


    def get_pending_for_question(
        self,
        question_id: int,
    ) -> SearchAttempt | None:

        return (
            self.db.query(SearchAttempt)
            .filter(
                SearchAttempt.research_question_id
                == question_id,
                SearchAttempt.status
                == "pending",
            )
            .order_by(
                SearchAttempt.id
            )
            .first()
        )

    def get_active_for_question(
        self,
        question_id: int,
    ) -> SearchAttempt | None:

        return (
            self.db.query(SearchAttempt)
            .filter(
                SearchAttempt.research_question_id
                == question_id,
                SearchAttempt.status.in_(
                    {
                        "pending",
                        "running",
                    }
                ),
            )
            .order_by(
                SearchAttempt.id
            )
            .first()
        )

    def mark_running(
        self,
        attempt_id: int,
    ) -> None:

        attempt = self.get(
            attempt_id
        )

        if attempt is None:
            raise ValueError(
                "Search attempt not found."
            )

        if attempt.status == "running":
            return

        if attempt.status != "pending":
            raise ValueError(
                "Only a pending search attempt "
                "can be marked as running."
            )

        attempt.status = "running"

        attempt.updated_at = datetime.now(
            timezone.utc
        )

        try:

            self.db.commit()

        except Exception:

            self.db.rollback()

            raise


    def mark_completed(
        self,
        attempt_id: int,
    ) -> None:

        try:

            self.set_completed(
                attempt_id
            )

            self.db.commit()

        except Exception:

            self.db.rollback()

            raise


    def set_completed(
        self,
        attempt_id: int,
    ) -> None:

        attempt = self.get(
            attempt_id
        )

        if attempt is None:
            raise ValueError(
                "Search attempt not found."
            )

        if attempt.status == "completed":
            return

        if attempt.status != "running":
            raise ValueError(
                "Only a running search attempt "
                "can be marked as completed."
            )

        now = datetime.now(
            timezone.utc
        )

        attempt.status = "completed"
        attempt.updated_at = now
        attempt.completed_at = now


    
    def resolve_search_attempt_fenced(
        self,
        session_id: str,
        question_id: int,
        lease: ExecutionLease,
    ) -> tuple[bool, int | None]:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            #
            # Fence execution before reading or
            # changing durable attempt state.
            #

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            #
            # Lock the research question while
            # resolving its search attempt.
            #

            question_row = self.db.execute(
                text(
                    """
                    SELECT id
                    FROM dbo.research_questions
                        WITH (UPDLOCK, HOLDLOCK)
                    WHERE id = :question_id
                    AND research_session_id = :session_id
                    """
                ),
                {
                    "question_id": question_id,
                    "session_id": session_id,
                },
            ).first()

            if question_row is None:

                raise ValueError(
                    "Research question does not belong "
                    "to the execution session."
                )

            #
            # Recover an outstanding attempt first.
            #

            active_attempt = (
                self.get_active_for_question(
                    question_id
                )
            )

            if active_attempt is not None:

                if (
                    active_attempt.research_session_id
                    != session_id
                ):

                    raise ValueError(
                        "Search attempt belongs to "
                        "another research session."
                    )

                if active_attempt.status == "pending":

                    active_attempt.status = "running"

                    active_attempt.updated_at = (
                        datetime.now(
                            timezone.utc
                        )
                    )

                elif active_attempt.status != "running":

                    raise ValueError(
                        "Unexpected active search "
                        "attempt status."
                    )

                attempt_id = active_attempt.id

                self.db.commit()

                return True, attempt_id

            #
            # Recover the latest completed attempt.
            #
            # Ordering by descending ID selects
            # the most recently created attempt.
            #

            completed_attempt_row = self.db.execute(
                text(
                    """
                    SELECT TOP (1)
                        id
                    FROM dbo.search_attempts
                    WHERE research_session_id = :session_id
                    AND research_question_id = :question_id
                    AND status = 'completed'
                    ORDER BY id DESC
                    """
                ),
                {
                    "session_id": session_id,
                    "question_id": question_id,
                },
            ).first()

            if completed_attempt_row is not None:

                attempt_id = completed_attempt_row.id

                self.db.commit()

                return False, attempt_id

            #
            # Preserve the existing behaviour for
            # historical attempts that are not
            # currently active or completed.
            #

            if self.has_attempts_for_question(
                question_id
            ):

                self.db.commit()

                return False, None

            #
            # Legacy compatibility for research
            # completed before search attempts
            # were introduced.
            #

            if SearchRepository(
                self.db
            ).has_results_for_question(
                question_id
            ):

                self.db.commit()

                return False, None

            #
            # No attempt history or legacy results.
            # Create the initial search attempt.
            #

            attempt = self.add(
                session_id=session_id,
                question_id=question_id,
                purpose="initial",
            )

            attempt.status = "running"

            attempt.updated_at = datetime.now(
                timezone.utc
            )

            self.db.flush()

            attempt_id = attempt.id

            self.db.commit()

            return True, attempt_id

        except Exception:

            self.db.rollback()

            raise
