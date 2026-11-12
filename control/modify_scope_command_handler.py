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
    ControlContext,
    ModifyScopeResult,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class ModifyScopeCommandHandler:

    def __init__(
        self,
        session_factory,
    ):
        self.session_factory = session_factory

    def execute(
        self,
        command: ControlCommand,
        context: ControlContext,
    ) -> ModifyScopeResult:

        if context.session_id is None:
            raise ValueError(
                "modify_scope requires an "
                "active research session."
            )

        if command.scope is None:
            raise ValueError(
                "modify_scope requires a "
                "replacement research scope."
            )

        scope = command.scope.strip()

        if not scope:
            raise ValueError(
                "Research scope cannot be empty."
            )

        #
        # Scope changes are currently permitted only
        # while research evidence is still mutable.
        #
        # We deliberately do not allow reviewed or
        # completed research to be reinterpreted under
        # a new scope until review/report versioning
        # exists.
        #

        allowed_statuses = {
            "researching",
            "researched",
        }

        if context.status not in allowed_statuses:
            raise ValueError(
                "Research scope cannot be modified "
                "while the session status is "
                f"'{context.status}'."
            )

        with self.session_factory() as db:

            repository = (
                ResearchSessionRepository(db)
            )

            research_session = (
                repository.get(
                    context.session_id
                )
            )

            if research_session is None:
                raise ValueError(
                    "Research session not found: "
                    f"{context.session_id}"
                )

            #
            # Re-check the authoritative lifecycle
            # state inside the execution transaction.
            #
            # ControlContext was authoritative when
            # created, but it may have become stale
            # before handler execution.
            #

            if (
                research_session.status
                not in allowed_statuses
            ):
                raise ValueError(
                    "Research scope cannot be modified "
                    "while the session status is "
                    f"'{research_session.status}'."
                )

            research_session = (
                repository.set_scope(
                    session_id=(
                        research_session.id
                    ),
                    scope=scope,
                )
            )

            return ModifyScopeResult(
                session_id=research_session.id,
                topic=research_session.topic,
                scope=research_session.scope,
                status=research_session.status,
            )