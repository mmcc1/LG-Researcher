from domain.control import (
    AddQuestionResult,
    ControlCommand,
    ControlContext,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class AddQuestionCommandHandler:

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
        context: ControlContext,
    ) -> AddQuestionResult:

        if context.session_id is None:
            raise ValueError(
                "An active research session "
                "is required."
            )

        if command.question is None:
            raise ValueError(
                "A research question is required."
            )

        question_text = (
            command.question.strip()
        )

        if not question_text:
            raise ValueError(
                "A research question is required."
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
                    "Research session not found."
                )

            #
            # Recheck the authoritative lifecycle
            # immediately before mutation.
            #
            # The lifecycle policy has already
            # checked ControlContext, but SQL is
            # authoritative at the write boundary.
            #

            if (
                research_session.status
                == "completed"
            ):

                raise ValueError(
                    "Questions cannot currently "
                    "be added to a completed "
                    "research session."
                )

            research_question = (
                repository.add_question(
                    session_id=(
                        research_session.id
                    ),
                    question=question_text,
                )
            )

            return AddQuestionResult(
                question_id=(
                    research_question.id
                ),
                session_id=(
                    research_session.id
                ),
                question=(
                    research_question.question
                ),
                status=(
                    research_question.status
                ),
            )