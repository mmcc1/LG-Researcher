from domain.control import (
    ControlCommand,
    ControlContext,
)


class ControlLifecyclePolicy:

    def validate(
        self,
        command: ControlCommand,
        context: ControlContext,
    ) -> None:

        operation = command.operation
        status = context.status

        #
        # Commands that do not depend on an
        # existing session lifecycle.
        #

        if operation in {
            "help",
            "start_research",
        }:
            return

        if context.session_id is None:
            raise ValueError(
                f"Operation '{operation}' requires "
                "an active research session."
            )

        if status is None:
            raise ValueError(
                "The active research session has "
                "no lifecycle status."
            )

        #
        # Read-only.
        #

        if operation == "status":
            return

        #
        # Add question.
        #
        # A new question can currently only be added
        # before the session enters the review phase.
        #

        if operation == "add_question":

            if status not in {
                "planned",
                "researching",
                "researched",
            }:
                raise ValueError(
                    "Questions can only be added "
                    "before the research session "
                    "enters review."
                )

            return

        #
        # Additional research.
        #
        # Deeper research and counter-evidence both
        # add evidence to an existing researched
        # question.
        #
        # They may therefore run while the overall
        # session is still researching, or after all
        # initial research has completed.
        #
        # The command handler performs the stronger
        # question-level check that the target
        # ResearchQuestion itself is "researched".
        #
        # Once review begins, additional evidence is
        # prohibited until review/report invalidation
        # or versioning semantics are implemented.
        #

        if operation in {
            "deeper_research",
            "counter_evidence",
        }:

            if status not in {
                "researching",
                "researched",
            }:
                raise ValueError(
                    f"Operation '{operation}' can "
                    "only be requested for research "
                    "that has completed but has not "
                    "yet entered review."
                )

            return

        #
        # Modify scope.
        #
        # Scope modification currently changes the
        # durable boundaries governing future
        # research only.
        #
        # We allow it while research evidence remains
        # mutable, but not once review has begun.
        #
        # A planned session is deliberately excluded
        # for now because its questions were already
        # generated without the replacement scope.
        #
        # Pre-planning scope support will be added
        # when ResearchPlanner becomes scope-aware.
        #

        if operation == "modify_scope":

            if status not in {
                "researching",
                "researched",
            }:
                raise ValueError(
                    "Research scope can only be "
                    "modified while the session is "
                    "researching or researched and "
                    "has not entered review."
                )

            return

        #
        # Report generation.
        #

        if operation == "generate_report":

            if status not in {
                "reviewed",
                "reporting",
                "completed",
            }:
                raise ValueError(
                    "A report can only be generated "
                    "after research review has "
                    "completed."
                )

            return

        #
        # Pause.
        #

        if operation == "pause":

            if status not in {
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
                    f"status '{status}'."
                )

            return

        #
        # Resume.
        #

        if operation == "resume":

            if status == "completed":
                raise ValueError(
                    "A completed research session "
                    "cannot be resumed."
                )

            return

        raise ValueError(
            "No lifecycle policy exists for "
            f"operation '{operation}'."
        )