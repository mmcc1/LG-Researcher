
from sqlalchemy.orm import sessionmaker

from langchain_core.runnables import RunnableConfig

from graph.state import ResearchState

from persistence.execution_lease_repository import (
    ExecutionLease,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class CompleteQuestionNode:

    def __init__(
        self,
        session_factory: sessionmaker,
    ):

        self.session_factory = session_factory

    def __call__(
        self,
        state: ResearchState,
        config: RunnableConfig,
    ) -> dict:

        session_id = state[
            "session_id"
        ]

        question_id = state[
            "current_question_id"
        ]

        if question_id is None:

            raise ValueError(
                "Cannot complete question: "
                "no question is selected."
            )

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

            repository.set_question_status_fenced(
                session_id=session_id,
                question_id=question_id,
                status="researched",
                lease=lease,
            )

        print()

        print(
            f"Research question "
            f"{question_id} completed."
        )

        return {}
