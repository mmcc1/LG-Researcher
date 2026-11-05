from agents.control_agent import (
    ControlAgent,
)

from control.control_context_factory import (
    ControlContextFactory,
)

from control.status_command_handler import (
    StatusCommandHandler,
)

from domain.control import (
    ControlResult,
    ResearchExecutionResult,
    ResearchStatus,
)

from processing.control_command_validator import (
    ControlCommandValidator,
)

from processing.control_lifecycle_policy import (
    ControlLifecyclePolicy,
)

from control.help_command_handler import (
    HelpCommandHandler,
)

from control.start_research_command_handler import (
    StartResearchCommandHandler,
)

from control.resume_command_handler import (
    ResumeCommandHandler,
)

from control.generate_report_command_handler import (
    GenerateReportCommandHandler,
)

from control.add_question_command_handler import (
    AddQuestionCommandHandler,
)

from control.deeper_research_command_handler import (
    DeeperResearchCommandHandler,
)

from control.counter_evidence_command_handler import (
    CounterEvidenceCommandHandler,
)

from control.modify_scope_command_handler import (
    ModifyScopeCommandHandler,
)

from control.pause_command_handler import (
    PauseCommandHandler,
)


class ControlService:

    def __init__(
        self,
        control_agent: ControlAgent,
        context_factory: ControlContextFactory,
        command_validator: ControlCommandValidator,
        lifecycle_policy: ControlLifecyclePolicy,
        status_handler: StatusCommandHandler,
        help_handler: HelpCommandHandler,
        start_research_handler: StartResearchCommandHandler,
        resume_handler: ResumeCommandHandler,
        generate_report_handler: GenerateReportCommandHandler,
        add_question_handler: AddQuestionCommandHandler,
        modify_scope_handler: ModifyScopeCommandHandler,
        deeper_research_handler: DeeperResearchCommandHandler,
        counter_evidence_handler: CounterEvidenceCommandHandler,
        pause_handler: PauseCommandHandler,
    ):
        self.control_agent = control_agent
        self.context_factory = context_factory
        self.command_validator = command_validator
        self.lifecycle_policy = lifecycle_policy
        self.status_handler = status_handler
        self.help_handler = help_handler

        self.start_research_handler = (
            start_research_handler
        )

        self.resume_handler = (
            resume_handler
        )

        self.generate_report_handler = (
            generate_report_handler
        )

        self.add_question_handler = (
            add_question_handler
        )

        self.deeper_research_handler = (
            deeper_research_handler
        )

        self.counter_evidence_handler = (
            counter_evidence_handler
        )

        self.modify_scope_handler = (
            modify_scope_handler
        )

        self.pause_handler = (
            pause_handler
        )

    def execute(
        self,
        user_message: str,
        session_id: str | None,
    ) -> ControlResult:

        #
        # 1. Build the trusted context from SQL.
        #

        context = (
            self.context_factory.create(
                session_id=session_id,
            )
        )

        #
        # 2. Ask the Control Agent to interpret
        #    the user's natural-language request.
        #

        raw_command = (
            self.control_agent.interpret(
                user_message=user_message,
                context=context,
            )
        )

        #
        # 3. Structurally validate and
        #    canonicalise the command.
        #

        command = (
            self.command_validator.validate(
                command=raw_command,
                context=context,
            )
        )

        #
        # 4. Check whether this operation is
        #    allowed in the current lifecycle.
        #

        self.lifecycle_policy.validate(
            command=command,
            context=context,
        )

        #
        # 5. Execute the appropriate handler.
        #

        if command.operation == "status":

            status = self.status_handler.execute(
                context=context,
            )

            return ControlResult(
                operation=command.operation,
                success=True,
                message=(
                    self._research_status_message(
                        status=status,
                    )
                ),
                status=status,
            )

        if command.operation == "help":

            help_result = (
                self.help_handler.execute()
            )

            return ControlResult(
                operation=command.operation,
                success=True,
                message=(
                    "Available research operations retrieved."
                ),
                help=help_result,
            )

        if command.operation == "start_research":

            research = (
                self.start_research_handler.execute(
                    command=command,
                )
            )

            return ControlResult(
                operation=command.operation,
                success=True,
                message=(
                    self._research_execution_message(
                        operation=command.operation,
                        research=research,
                    )
                ),
                research=research,
            )

        if command.operation == "resume":

            research = (
                self.resume_handler.execute(
                    context=context,
                )
            )

            return ControlResult(
                operation=command.operation,
                success=True,
                message=(
                    self._research_execution_message(
                        operation=command.operation,
                        research=research,
                    )
                ),
                research=research,
            )

        if command.operation == "generate_report":

            report = (
                self.generate_report_handler.execute(
                    context=context,
                )
            )

            return ControlResult(
                operation=command.operation,
                success=True,
                message=(
                    "Research report retrieved."
                ),
                report=report,
            )

        if command.operation == "add_question":

            question = (
                self.add_question_handler.execute(
                    command=command,
                    context=context,
                )
            )

            return ControlResult(
                operation=command.operation,
                success=True,
                message=(
                    "Research question added."
                ),
                question=question,
            )

        if command.operation == "deeper_research":

            deeper_research = (
                self.deeper_research_handler.execute(
                    command=command,
                    context=context,
                )
            )

            return ControlResult(
                operation=command.operation,
                success=True,
                message=(
                    "Deeper research scheduled."
                ),
                deeper_research=deeper_research,
            )

        if command.operation == "counter_evidence":

            counter_evidence = (
                self.counter_evidence_handler.execute(
                    command=command,
                    context=context,
                )
            )

            return ControlResult(
                operation=command.operation,
                success=True,
                message=(
                    "Counter-evidence research scheduled."
                ),
                counter_evidence=counter_evidence,
            )

        if command.operation == "modify_scope":

            scope = (
                self.modify_scope_handler.execute(
                    command=command,
                    context=context,
                )
            )

            return ControlResult(
                operation=command.operation,
                success=True,
                message=(
                    "Research scope modified."
                ),
                scope=scope,
            )

        if command.operation == "pause":

            if context.session_id is None:
                raise ValueError(
                    "Pause requires an active "
                    "research session."
                )

            pause = (
                self.pause_handler.execute(
                    command=command,
                    session_id=context.session_id,
                )
            )

            return ControlResult(
                operation=command.operation,
                success=True,
                message=(
                    "Research pause requested."
                ),
                pause=pause,
            )

        raise ValueError(
            "Control operation is recognised "
            "but does not yet have an "
            "executable handler: "
            f"{command.operation}"
        )


    @staticmethod
    def _research_status_message(
        status: ResearchStatus,
    ) -> str:

        #
        # Build the lifecycle description first.
        #
        # pause_requested is deliberately handled
        # separately because pause is not itself a
        # lifecycle status.
        #

        if status.status == "created":

            lifecycle_message = (
                "The research session has been created."
            )

        elif status.status == "planning":

            lifecycle_message = (
                "Research planning is in progress."
            )

        elif status.status == "planned":

            if (
                status.researching_questions > 0
                or status.researched_questions > 0
                or status.reviewing_questions > 0
                or status.reviewed_questions > 0
            ):

                completed_questions = (
                    status.researched_questions
                    + status.reviewing_questions
                    + status.reviewed_questions
                )

                lifecycle_message = (
                    "Research is in progress. "
                    f"{completed_questions} of "
                    f"{status.total_questions} questions "
                    "have been researched."
                )

            elif status.total_questions == 0:

                lifecycle_message = (
                    "Research planning is complete."
                )

            elif status.pending_questions == 1:

                lifecycle_message = (
                    "Research planning is complete. "
                    "1 question is pending."
                )

            else:

                lifecycle_message = (
                    "Research planning is complete. "
                    f"{status.pending_questions} "
                    "questions are pending."
                )

        elif status.status == "researching":

            completed_questions = (
                status.researched_questions
                + status.reviewing_questions
                + status.reviewed_questions
            )

            lifecycle_message = (
                "Research is in progress. "
                f"{completed_questions} of "
                f"{status.total_questions} questions "
                "have been researched."
            )

        elif status.status == "researched":

            lifecycle_message = (
                "Research is complete for all "
                f"{status.total_questions} questions."
            )

        elif status.status == "reviewing":

            lifecycle_message = (
                "Research review is in progress. "
                f"{status.reviewed_questions} of "
                f"{status.total_questions} questions "
                "have been reviewed."
            )

        elif status.status == "reviewed":

            lifecycle_message = (
                "Research review is complete for all "
                f"{status.total_questions} questions."
            )

        elif status.status == "reporting":

            if status.report_available:

                lifecycle_message = (
                    "The research report has been "
                    "generated and is awaiting workflow "
                    "completion."
                )

            else:

                lifecycle_message = (
                    "Research report generation is "
                    "in progress."
                )

        elif status.status == "completed":

            if status.report_available:

                lifecycle_message = (
                    "Research is complete and the "
                    "report is available."
                )

            else:

                lifecycle_message = (
                    "Research is complete."
                )

        else:

            lifecycle_message = (
                "Research session status: "
                f"{status.status}."
            )

        #
        # Cooperative pause is orthogonal to the
        # lifecycle phase.
        #

        if status.pause_requested:

            return (
                "Research is paused at a safe "
                "workflow boundary. "
                + lifecycle_message
            )

        return lifecycle_message

    @staticmethod
    def _research_execution_message(
        operation: str,
        research: ResearchExecutionResult,
    ) -> str:

        #
        # A completed lifecycle always takes
        # precedence. A completed workflow is no
        # longer meaningfully suspended.
        #

        if research.status == "completed":

            if operation == "resume":
                return (
                    "Research workflow resumed "
                    "and completed."
                )

            return (
                "Research workflow completed."
            )

        #
        # The workflow returned because a durable
        # cooperative pause was observed.
        #

        if research.pause_requested:

            return (
                "Research workflow stopped at a "
                "safe pause boundary. "
                f"Current phase: {research.status}."
            )

        #
        # Execution returned without completion
        # and without an active pause request.
        #
        # This can legitimately occur for
        # execution targets that intentionally
        # stop before the full workflow completes.
        #

        if operation == "resume":

            return (
                "Research workflow resumed. "
                f"Current phase: {research.status}."
            )

        return (
            "Research workflow returned. "
            f"Current phase: {research.status}."
        )