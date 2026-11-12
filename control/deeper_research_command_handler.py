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
    DeeperResearchResult,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)


class DeeperResearchCommandHandler:

    def __init__(
        self,
        session_factory,
    ):
        self.session_factory = session_factory

    def execute(
        self,
        command: ControlCommand,
        context: ControlContext,
    ) -> DeeperResearchResult:

        if context.session_id is None:
            raise ValueError(
                "deeper_research requires "
                "an active research session."
            )

        if command.question is None:
            raise ValueError(
                "deeper_research requires the "
                "research question to be identified."
            )

        with self.session_factory() as db:

            session_repository = (
                ResearchSessionRepository(db)
            )

            attempt_repository = (
                SearchAttemptRepository(db)
            )

            research_session = (
                session_repository.get(
                    context.session_id
                )
            )

            if research_session is None:
                raise ValueError(
                    "Research session not found."
                )

            if research_session.status not in {
                "researching",
                "researched",
            }:
                raise ValueError(
                    "Deeper research can only be "
                    "requested for research that has "
                    "completed but has not yet "
                    "entered review."
                )

            question = (
                session_repository
                .find_question_by_text(
                    session_id=context.session_id,
                    question_text=command.question,
                )
            )

            if question is None:
                raise ValueError(
                    "The requested research question "
                    "could not be matched exactly to "
                    "a question in the active session."
                )

            if question.status != "researched":
                raise ValueError(
                    "Deeper research can only be "
                    "requested for a question whose "
                    "current research pass has "
                    "completed."
                )

            try:

                #
                # All three durable changes belong
                # to one transaction.
                #

                attempt = (
                    attempt_repository.add(
                        session_id=context.session_id,
                        question_id=question.id,
                        purpose="deeper_research",
                        instructions=(
                            command.instructions
                        ),
                    )
                )

                session_repository\
                    .set_question_status_pending_commit(
                        question.id,
                        "pending",
                    )

                session_repository\
                    .set_status_pending_commit(
                        context.session_id,
                        "researching",
                    )

                attempt_id = attempt.id
                attempt_instructions = attempt.instructions
                question_text = question.question

                db.commit()

            except Exception:

                db.rollback()

                raise

            return DeeperResearchResult(
                search_attempt_id=attempt_id,
                session_id=context.session_id,
                question_id=question.id,
                question=question_text,
                instructions=attempt_instructions,
                status="pending",
            )