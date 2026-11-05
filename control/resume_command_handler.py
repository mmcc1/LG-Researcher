from application.research_workflow_service import (
    ResearchWorkflowService,
)

from domain.control import (
    ControlContext,
    ResearchExecutionResult,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class ResumeCommandHandler:

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
        context: ControlContext,
    ) -> ResearchExecutionResult:

        if context.session_id is None:
            raise ValueError(
                "An active research session "
                "is required."
            )

        session_id = (
            context.session_id
        )

        #
        # A cooperative pause remains durable until
        # the user explicitly requests resume.
        #
        # Clear that pause before invoking the
        # workflow. Otherwise the resumed graph
        # would encounter the next pause boundary
        # and terminate again.
        #
        # This does not change the lifecycle status.
        # The persisted status continues to identify
        # the phase from which the existing resume
        # machinery should recover.
        #

        with self.session_factory() as db:

            repository = (
                ResearchSessionRepository(db)
            )

            repository.clear_pause_request(
                session_id
            )

        #
        # Resume through the application workflow
        # boundary. The workflow service reloads
        # authoritative session information from SQL.
        #

        workflow_result = (
            self.workflow_service.resume(
                session_id=session_id,
            )
        )

        #
        # Reload authoritative lifecycle state
        # after execution.
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
                session_id=research_session.id,
                topic=research_session.topic,
                status=research_session.status,
                pause_requested=(
                    research_session.pause_requested
                ),
            )