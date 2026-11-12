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
    ResearchStatus,
)

from persistence.report_repository import (
    ReportRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class StatusCommandHandler:

    def __init__(
        self,
        session_factory,
    ):
        self.session_factory = session_factory

    def execute(
        self,
        context: ControlContext,
    ) -> ResearchStatus:

        if context.session_id is None:
            raise ValueError(
                "Status requires an active "
                "research session."
            )

        with self.session_factory() as db:

            session_repository = (
                ResearchSessionRepository(db)
            )

            report_repository = (
                ReportRepository(db)
            )

            research_session = (
                session_repository.get(
                    context.session_id
                )
            )

            if research_session is None:
                raise ValueError(
                    "Research session not found: "
                    f"{context.session_id}"
                )

            questions = (
                session_repository.get_questions(
                    context.session_id
                )
            )

            counts = {
                "pending": 0,
                "researching": 0,
                "researched": 0,
                "reviewing": 0,
                "reviewed": 0,
            }

            for question in questions:

                if question.status in counts:
                    counts[question.status] += 1

            report_available = (
                report_repository.exists_for_session(
                    context.session_id
                )
            )

            return ResearchStatus(
                session_id=research_session.id,
                topic=research_session.topic,
                status=research_session.status,

                pause_requested=(
                    research_session.pause_requested
                ),

                total_questions=len(questions),

                pending_questions=counts["pending"],
                researching_questions=counts[
                    "researching"
                ],
                researched_questions=counts[
                    "researched"
                ],
                reviewing_questions=counts[
                    "reviewing"
                ],
                reviewed_questions=counts[
                    "reviewed"
                ],

                report_available=report_available,
            )