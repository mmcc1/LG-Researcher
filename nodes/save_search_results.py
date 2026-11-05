
from sqlalchemy.orm import sessionmaker

from langchain_core.runnables import RunnableConfig

from graph.state import ResearchState

from persistence.execution_lease_repository import (
    ExecutionLease,
)

from persistence.search_repository import (
    SearchRepository,
)


class SaveSearchResultsNode:

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

        question_id = state[
            "current_question_id"
        ]

        if question_id is None:

            raise ValueError(
                "No research question selected."
            )

        attempt_id = state.get(
            "current_search_attempt_id"
        )

        if attempt_id is None:

            raise ValueError(
                "No active search attempt "
                "is associated with this search."
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

            SearchRepository(
                db
            ).save_attempt_results(
                session_id=session_id,
                question_id=question_id,
                attempt_id=attempt_id,
                results=state["search_results"],
                lease=lease,
            )

        print(
            "Search results persisted and "
            "search attempt completed. "
            f"Attempt ID: {attempt_id}."
        )

        return {}
