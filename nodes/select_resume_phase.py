
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
    ExecutionLeaseRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class SelectResumePhaseNode:

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

        with self.session_factory() as db:

            try:

                ExecutionLeaseRepository(
                    db
                ).fence(
                    lease
                )

                repository = (
                    ResearchSessionRepository(db)
                )

                research_session = (
                    repository.get(
                        session_id
                    )
                )

                if research_session is None:

                    raise ValueError(
                        "Research session not found: "
                        f"{session_id}"
                    )

                status = research_session.status

                db.commit()

            except Exception:

                db.rollback()

                raise

        return {
            "resume_phase": status,
        }
