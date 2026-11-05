from application.research_workflow_service import (
    ResearchWorkflowService,
)

from control.generate_report_command_handler import (
    GenerateReportCommandHandler,
)

from domain.control import (
    ControlContext,
)

from persistence.database import (
    SessionLocal,
)


SESSION_ID = (
    "8b89d73a-c2b5-4b15-a6c5-bb71e43064b5"
)


#
# This workflow service must never be called for
# an already-completed session.
#

class FailIfCalledWorkflowService:

    def resume(
        self,
        session_id: str,
    ):

        raise AssertionError(
            "Workflow resume was called for "
            "a completed research session."
        )


handler = GenerateReportCommandHandler(
    workflow_service=FailIfCalledWorkflowService(),
    session_factory=SessionLocal,
)


context = ControlContext(
    session_id=SESSION_ID,
    topic=(
        "What cryptographic hash function "
        "does Bitcoin use for proof-of-work?"
    ),
    status="completed",
)


print()
print(
    "GENERATE REPORT HANDLER TEST"
)
print(
    "============================"
)


result = handler.execute(
    context=context,
)


print()
print(
    result.model_dump_json(
        indent=2
    )
)


assert result.session_id == SESSION_ID

assert result.report_id == 2


print()
print(
    "PASS: existing report returned "
    "without invoking the workflow."
)