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
    ControlCommand,
    PauseResult,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class PauseCommandHandler:

    def __init__(
        self,
        session_factory,
    ):
        self.session_factory = (
            session_factory
        )

    def execute(
        self,
        command: ControlCommand,
        session_id: str,
    ) -> PauseResult:

        if command.operation != "pause":
            raise ValueError(
                "PauseCommandHandler only handles "
                "the pause operation."
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

            #
            # Recheck authoritative SQL state.
            #
            # ControlLifecyclePolicy validated the
            # context snapshot, but lifecycle state
            # may have changed before execution.
            #

            if research_session.status not in {
                "planning",
                "planned",
                "researching",
                "researched",
                "reviewing",
                "reviewed",
                "reporting",
            }:
                raise ValueError(
                    "The research session cannot be "
                    "paused from its current lifecycle "
                    f"status '{research_session.status}'."
                )

            research_session = (
                repository.request_pause(
                    session_id
                )
            )

            return PauseResult(
                session_id=research_session.id,
                topic=research_session.topic,
                status=research_session.status,
                pause_requested=(
                    research_session.pause_requested
                ),
            )