
from sqlalchemy.orm import (
    sessionmaker,
)

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


class CompleteReportNode:

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

        session_id = state["session_id"]

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

        #
        # The repository validates the lease,
        # verifies durable report existence,
        # and completes the session atomically.
        #

        with self.session_factory() as db:

            session_repository = (
                ResearchSessionRepository(db)
            )

            session_repository.complete_report_fenced(
                session_id=session_id,
                lease=lease,
            )

        print()
        print(
            "Research session completed."
        )

        return {}
