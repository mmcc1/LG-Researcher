
from sqlalchemy.orm import sessionmaker

from langchain_core.runnables import RunnableConfig

from graph.state import ResearchState

from persistence.execution_lease_repository import (
    ExecutionLease,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class SelectQuestionNode:

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

        session_id = state["session_id"]

        configurable = config.get(
            "configurable",
            {},
        )

        lease = configurable.get(
            "execution_lease"
        )

        execution_guard = configurable.get(
            "execution_guard"
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

        if (
            execution_guard is not None
            and not callable(execution_guard)
        ):

            raise TypeError(
                "Execution guard must be callable."
            )

        if execution_guard is not None:
            execution_guard()

        with self.session_factory() as db:

            repository = (
                ResearchSessionRepository(db)
            )

            question = (
                repository.select_question_fenced(
                    session_id=session_id,
                    lease=lease,
                )
            )

            if question is None:

                question_id = None
                question_text = None

            else:

                question_id = question.id
                question_text = question.question

        if execution_guard is not None:
            execution_guard()

        if question_id is None:

            print()
            print(
                "No remaining research questions."
            )

            return {
                "current_question_id": None,
                "current_question": None,
                "current_search_attempt_id": None,
            }

        print()
        print(
            f"Selected research question "
            f"{question_id}:"
        )
        print(question_text)

        return {
            "current_question_id": question_id,
            "current_question": question_text,
            "current_search_attempt_id": None,
        }
