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