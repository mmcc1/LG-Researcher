from sqlalchemy.orm import (
    sessionmaker,
)

from langchain_core.runnables import (
    RunnableConfig,
)

from agents.research_scope_agent import (
    ResearchScopeAgent,
)

from graph.state import (
    ResearchState,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)

from persistence.research_scope_repository import (
    ResearchScopeRepository,
)


class DefineResearchScopeNode:

    def __init__(
        self,
        session_factory: sessionmaker,
        agent: ResearchScopeAgent,
    ):

        self.session_factory = (
            session_factory
        )

        self.agent = agent

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

                repository = ResearchScopeRepository(
                    db
                )

                definition = repository.get(
                    session_id
                )

                db.commit()

            except Exception:

                db.rollback()

                raise

        if definition is not None:

            return {
                "scope_definition": definition
            }

        definition = self.agent.define_scope(
            topic=state["topic"],
            scope=state.get("scope"),
            user_questions=state.get(
                "user_questions"
            ),
        )

        with self.session_factory() as db:

            repository = ResearchScopeRepository(
                db
            )

            persisted_definition = repository.save(
                session_id=session_id,
                definition=definition,
                lease=lease,
            )

        return {
            "scope_definition": persisted_definition
        }