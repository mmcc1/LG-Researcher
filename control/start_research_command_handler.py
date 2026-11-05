from application.research_workflow_service import (
    ResearchWorkflowService,
)

from domain.control import (
    ControlCommand,
    ResearchExecutionResult,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class StartResearchCommandHandler:

    def __init__(
        self,
        workflow_service: ResearchWorkflowService,
        session_factory,
    ):
        self.workflow_service = (
            workflow_service
        )

        self.session_factory = (
            session_factory
        )

    def execute(
        self,
        command: ControlCommand,
    ) -> ResearchExecutionResult:

        if command.topic is None:
            raise ValueError(
                "A research topic is required."
            )

        #
        # The workflow service owns creation and
        # execution of the research workflow.
        #

        workflow_result = (
            self.workflow_service.start(
                topic=command.topic,
                scope=command.scope,
            )
)

        #
        # Reload authoritative lifecycle status
        # after workflow execution.
        #

        with self.session_factory() as db:

            repository = (
                ResearchSessionRepository(db)
            )

            research_session = (
                repository.get(
                    workflow_result.session_id
                )
            )

            if research_session is None:
                raise ValueError(
                    "Research session disappeared "
                    "after workflow execution."
                )

            return ResearchExecutionResult(
                session_id=(
                    research_session.id
                ),
                topic=(
                    research_session.topic
                ),
                status=(
                    research_session.status
                ),
                pause_requested=(
                    research_session.pause_requested
                ),
            )