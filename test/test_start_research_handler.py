from domain.control import (
    ControlCommand,
)

from domain.workflow import (
    ResearchWorkflowResult,
)

from control.start_research_command_handler import (
    StartResearchCommandHandler,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class FakeWorkflowService:

    def start(
        self,
        topic: str,
    ) -> ResearchWorkflowResult:

        #
        # Simulate what the real workflow service
        # does, without invoking LangGraph or an LLM.
        #

        with SessionLocal() as db:

            repository = (
                ResearchSessionRepository(db)
            )

            research_session = (
                repository.create(
                    topic=topic
                )
            )

            repository.set_status(
                research_session.id,
                "planning",
            )

            session_id = (
                research_session.id
            )

        return ResearchWorkflowResult(
            session_id=session_id,
            topic=topic,
            graph_result={},
        )


handler = StartResearchCommandHandler(
    workflow_service=FakeWorkflowService(),
    session_factory=SessionLocal,
)


command = ControlCommand(
    operation="start_research",
    topic="Test control workflow",
)


result = handler.execute(
    command=command,
)


print()
print(
    "START RESEARCH HANDLER RESULT"
)
print(
    "============================="
)

print(
    result.model_dump_json(
        indent=2
    )
)