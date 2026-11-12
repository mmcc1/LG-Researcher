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

from langchain_core.runnables import (
    RunnableConfig,
)

from graph.state import (
    ResearchState,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
)

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)


class CheckExistingSearchNode:

    def __init__(
        self,
        session_factory,
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
                "No current research question."
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
                SearchAttemptRepository(db)
            )

            (
                search_required,
                attempt_id,
            ) = repository.resolve_search_attempt_fenced(
                session_id=session_id,
                question_id=question_id,
                lease=lease,
            )

        if search_required:

            print(
                "Search attempt ready. "
                f"Attempt ID: {attempt_id}. "
                "Search required."
            )

        elif attempt_id is not None:

            print(
                "Reusing completed search attempt. "
                f"Attempt ID: {attempt_id}. "
                "Search not required."
            )

        else:

            print(
                "No search attempt selected. "
                "Search not required."
            )

        return {
            "search_required": search_required,
            "current_search_attempt_id": attempt_id,
        }
