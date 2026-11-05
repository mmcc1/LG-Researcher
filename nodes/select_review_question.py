
from sqlalchemy.orm import sessionmaker

from langchain_core.runnables import (
    RunnableConfig,
)

from graph.state import (
    ResearchState,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class SelectReviewQuestionNode:

    def __init__(
        self,
        session_factory: sessionmaker,
    ):

        self.session_factory = (
            session_factory
        )

    def __call__(
        self,
        state: ResearchState,
        config: RunnableConfig,
    ) -> dict:

        session_id = state[
            "session_id"
        ]

        lease = config.get(
            "configurable",
            {},
        ).get(
            "execution_lease"
        )

        if not isinstance(
            lease,
            ExecutionLease,
        ):

            raise RuntimeError(
                "Execution lease is missing "
                "from graph configuration."
            )

        if lease.session_id != session_id:

            raise ValueError(
                "Execution lease does not match "
                "the research session."
            )

        with self.session_factory() as db:

            repository = (
                ResearchSessionRepository(db)
            )

            question = (
                repository
                .select_review_question_fenced(
                    session_id=session_id,
                    lease=lease,
                )
            )

            if question is None:

                return {
                    "current_review_question_id": None,
                    "current_review_question": None,
                }

            question_id = question.id
            question_text = question.question

        return {
            "current_review_question_id": question_id,
            "current_review_question": question_text,
        }
