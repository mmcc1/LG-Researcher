from domain.control import (
    ResearchExecutionResult,
)

from control.control_service import (
    ControlService,
)


def make_result(
    status: str,
    pause_requested: bool = False,
):

    return ResearchExecutionResult(
        session_id="test-session",
        topic="Test topic",
        status=status,
        pause_requested=pause_requested,
    )


print()
print("CONTROL EXECUTION MESSAGE TEST")
print("==============================")

#
# -------------------------------------------------
# TEST 1 - NORMAL COMPLETION
# -------------------------------------------------
#

print()
print("TEST 1 - NORMAL COMPLETION")
print("--------------------------")


message = (
    ControlService
    ._research_execution_message(
        operation="start_research",
        research=make_result(
            status="completed",
        ),
    )
)


assert (
    message
    == "Research workflow completed."
)


print(
    "Start completion message: PASSED"
)


#
# -------------------------------------------------
# TEST 2 - RESUME TO COMPLETION
# -------------------------------------------------
#

print()
print("TEST 2 - RESUME TO COMPLETION")
print("-----------------------------")


message = (
    ControlService
    ._research_execution_message(
        operation="resume",
        research=make_result(
            status="completed",
        ),
    )
)


assert (
    message
    ==
    "Research workflow resumed and completed."
)


print(
    "Resume completion message: PASSED"
)


#
# -------------------------------------------------
# TEST 3 - PAUSED AFTER PLANNING
# -------------------------------------------------
#

print()
print("TEST 3 - PAUSED AFTER PLANNING")
print("------------------------------")


message = (
    ControlService
    ._research_execution_message(
        operation="start_research",
        research=make_result(
            status="planned",
            pause_requested=True,
        ),
    )
)


assert (
    message
    ==
    "Research workflow stopped at a "
    "safe pause boundary. "
    "Current phase: planned."
)


print(
    "Planning pause message: PASSED"
)


#
# -------------------------------------------------
# TEST 4 - PAUSED DURING RESEARCH
# -------------------------------------------------
#

print()
print("TEST 4 - PAUSED DURING RESEARCH")
print("--------------------------------")


message = (
    ControlService
    ._research_execution_message(
        operation="resume",
        research=make_result(
            status="researching",
            pause_requested=True,
        ),
    )
)


assert (
    message
    ==
    "Research workflow stopped at a "
    "safe pause boundary. "
    "Current phase: researching."
)


print(
    "Research pause message: PASSED"
)


#
# -------------------------------------------------
# TEST 5 - RESUMED BUT NOT COMPLETED
# -------------------------------------------------
#

print()
print("TEST 5 - RESUMED, NOT COMPLETED")
print("--------------------------------")


message = (
    ControlService
    ._research_execution_message(
        operation="resume",
        research=make_result(
            status="researching",
            pause_requested=False,
        ),
    )
)


assert (
    message
    ==
    "Research workflow resumed. "
    "Current phase: researching."
)


print(
    "Non-completed resume message: PASSED"
)


#
# -------------------------------------------------
# TEST 6 - COMPLETED WINS OVER PAUSE FLAG
# -------------------------------------------------
#

print()
print("TEST 6 - COMPLETION PRECEDENCE")
print("------------------------------")


message = (
    ControlService
    ._research_execution_message(
        operation="resume",
        research=make_result(
            status="completed",
            pause_requested=True,
        ),
    )
)


assert (
    message
    ==
    "Research workflow resumed and completed."
)


print(
    "Completion precedence: PASSED"
)


print()
print("==============================")
print("PASS")
print("==============================")

print(
    "Control execution messages now reflect "
    "the actual post-execution lifecycle state."
)