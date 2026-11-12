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

from domain.control import (
    ControlContext,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class ControlContextFactory:

    def __init__(
        self,
        session_factory,
    ):
        self.session_factory = session_factory

    def create(
        self,
        session_id: str | None,
    ) -> ControlContext:

        if session_id is None:

            return ControlContext(
                session_id=None,
                topic=None,
                scope=None,
                status=None,
                pause_requested=False,
            )

        with self.session_factory() as db:

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

            return ControlContext(
                session_id=research_session.id,
                topic=research_session.topic,
                scope=research_session.scope,
                status=research_session.status,
                pause_requested=(
                    research_session.pause_requested
                ),
            )