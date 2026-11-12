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
