#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

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
