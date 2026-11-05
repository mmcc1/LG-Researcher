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