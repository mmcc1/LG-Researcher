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