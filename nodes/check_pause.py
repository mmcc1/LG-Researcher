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

from graph.state import (
    ResearchState,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class CheckPauseNode:

    def __init__(
        self,
        session_factory,
    ):
        self.session_factory = (
            session_factory
        )

    def __call__(
        self,
        state: ResearchState,
    ) -> dict:

        session_id = state[
            "session_id"
        ]

        with self.session_factory() as db:

            repository = (
                ResearchSessionRepository(db)
            )

            pause_requested = (
                repository.is_pause_requested(
                    session_id
                )
            )

        return {
            "pause_requested":
                pause_requested
        }