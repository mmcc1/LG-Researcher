from domain.control import (
    ControlCommand,
    ControlContext,
)


class ControlCommandValidator:

    def validate(
        self,
        command: ControlCommand,
        context: ControlContext,
    ) -> ControlCommand:

        operation = command.operation

        #
        # ---------------------------------------------
        # Operations requiring an active session
        # ---------------------------------------------
        #

        session_operations = {
            "status",
            "add_question",
            "modify_scope",
            "deeper_research",
            "counter_evidence",
            "generate_report",
            "pause",
            "resume",
        }

        if (
            operation in session_operations
            and context.session_id is None
        ):
            raise ValueError(
                f"Operation '{operation}' requires "
                "an active research session."
            )

                #
        # ---------------------------------------------
        # START RESEARCH
        # ---------------------------------------------
        #
        # A new research session may optionally define
        # a persistent research scope at creation time.
        #
        # The topic defines the overall subject.
        # The scope defines durable boundaries,
        # emphasis, focus, or exclusions within that
        # topic.
        #

        if operation == "start_research":

            if not command.topic:
                raise ValueError(
                    "start_research requires "
                    "a research topic."
                )

            topic = command.topic.strip()

            if not topic:
                raise ValueError(
                    "start_research requires "
                    "a non-empty research topic."
                )

            scope = command.scope

            if scope is not None:

                scope = scope.strip()

                if not scope:
                    scope = None

            return ControlCommand(
                operation=operation,
                topic=topic,
                question=None,
                scope=scope,
                instructions=command.instructions,
            )

        #
        # ---------------------------------------------
        # STATUS
        # ---------------------------------------------
        #

        if operation == "status":

            return ControlCommand(
                operation=operation,
                topic=None,
                question=None,
                scope=None,
                instructions=None,
            )

        #
        # ---------------------------------------------
        # ADD QUESTION
        # ---------------------------------------------
        #

        if operation == "add_question":

            if not command.question:
                raise ValueError(
                    "add_question requires "
                    "a research question."
                )

            return ControlCommand(
                operation=operation,
                topic=None,
                question=command.question,
                scope=None,
                instructions=command.instructions,
            )

        #
        # ---------------------------------------------
        # MODIFY SCOPE
        # ---------------------------------------------
        #
        # Scope is a first-class durable session
        # property.
        #
        # modify_scope replaces the complete current
        # scope. It does not change the fundamental
        # research topic and does not target an
        # individual research question.
        #

        if operation == "modify_scope":

            if not command.scope:
                raise ValueError(
                    "modify_scope requires a "
                    "replacement research scope."
                )

            scope = command.scope.strip()

            if not scope:
                raise ValueError(
                    "modify_scope requires a "
                    "non-empty replacement "
                    "research scope."
                )

            return ControlCommand(
                operation=operation,
                topic=None,
                question=None,
                scope=scope,
                instructions=None,
            )

        #
        # ---------------------------------------------
        # DEEPER RESEARCH
        # ---------------------------------------------
        #
        # The current implementation targets a
        # specific persisted ResearchQuestion.
        #
        # Instructions may refine the additional
        # discovery pass, but cannot identify the
        # target question by themselves.
        #

        if operation == "deeper_research":

            if not command.question:
                raise ValueError(
                    "deeper_research requires "
                    "a research question."
                )

            return ControlCommand(
                operation=operation,
                topic=None,
                question=command.question,
                scope=None,
                instructions=command.instructions,
            )

        #
        # ---------------------------------------------
        # COUNTER EVIDENCE
        # ---------------------------------------------
        #
        # Counter-evidence currently operates at the
        # ResearchQuestion level. Finding-level and
        # reviewed-claim-level targeting can be added
        # later without weakening this boundary.
        #

        if operation == "counter_evidence":

            if not command.question:
                raise ValueError(
                    "counter_evidence requires "
                    "a research question."
                )

            return ControlCommand(
                operation=operation,
                topic=None,
                question=command.question,
                scope=None,
                instructions=command.instructions,
            )

        #
        # ---------------------------------------------
        # GENERATE REPORT
        # ---------------------------------------------
        #

        if operation == "generate_report":

            return ControlCommand(
                operation=operation,
                topic=None,
                question=None,
                scope=None,
                instructions=None,
            )

        #
        # ---------------------------------------------
        # PAUSE
        # ---------------------------------------------
        #

        if operation == "pause":

            return ControlCommand(
                operation=operation,
                topic=None,
                question=None,
                scope=None,
                instructions=None,
            )

        #
        # ---------------------------------------------
        # RESUME
        # ---------------------------------------------
        #

        if operation == "resume":

            return ControlCommand(
                operation=operation,
                topic=None,
                question=None,
                scope=None,
                instructions=None,
            )

        #
        # ---------------------------------------------
        # HELP
        # ---------------------------------------------
        #

        if operation == "help":

            return ControlCommand(
                operation=operation,
                topic=None,
                question=None,
                scope=None,
                instructions=None,
            )

        raise ValueError(
            "Unsupported control operation: "
            f"{operation}"
        )