from control.control_service import (
    ControlService,
)

from domain.control import (
    ResearchStatus,
)


def make_status(
    *,
    status: str,
    pause_requested: bool = False,
    total_questions: int = 0,
    pending_questions: int = 0,
    researching_questions: int = 0,
    researched_questions: int = 0,
    reviewing_questions: int = 0,
    reviewed_questions: int = 0,
    report_available: bool = False,
) -> ResearchStatus:

    return ResearchStatus(
        session_id="test-session",
        topic="Test topic",
        status=status,
        pause_requested=pause_requested,
        total_questions=total_questions,
        pending_questions=pending_questions,
        researching_questions=(
            researching_questions
        ),
        researched_questions=(
            researched_questions
        ),
        reviewing_questions=(
            reviewing_questions
        ),
        reviewed_questions=(
            reviewed_questions
        ),
        report_available=report_available,
    )


print()
print("CONTROL STATUS MESSAGE TEST")
print("===========================")


#
# TEST 1 - PLANNING
#

print()
print("TEST 1 - PLANNING")
print("-----------------")


message = (
    ControlService._research_status_message(
        make_status(
            status="planning",
        )
    )
)

assert (
    message
    == "Research planning is in progress."
)

print("Planning message: PASSED")


#
# TEST 2 - PLANNED
#

print()
print("TEST 2 - PLANNED")
print("----------------")


message = (
    ControlService._research_status_message(
        make_status(
            status="planned",
            total_questions=4,
            pending_questions=4,
        )
    )
)

assert (
    message
    ==
    "Research planning is complete. "
    "4 questions are pending."
)

print("Planned message: PASSED")


#
# TEST 3 - PAUSED AFTER PLANNING
#

print()
print("TEST 3 - PAUSED")
print("---------------")


message = (
    ControlService._research_status_message(
        make_status(
            status="planned",
            pause_requested=True,
            total_questions=4,
            pending_questions=4,
        )
    )
)

assert (
    message
    ==
    "Research is paused at a safe "
    "workflow boundary. "
    "Research planning is complete. "
    "4 questions are pending."
)

print("Paused message: PASSED")


#
# TEST - PLANNED SESSION WITH ACTIVE RESEARCH
#
# A workflow interruption can leave the coarse
# session lifecycle at planned after a question
# has already transitioned to researching.
# Presentation must prefer the finer-grained
# durable question activity.
#


print()
print(
    "TEST - PLANNED WITH ACTIVE RESEARCH"
)

print(
    "-----------------------------------"
)


message = (
    ControlService._research_status_message(
        make_status(
            status="planned",
            pause_requested=False,
            total_questions=1,
            pending_questions=0,
            researching_questions=1,
        )
    )
)


assert (
    message
    ==
    "Research is in progress. "
    "0 of 1 questions have been researched."
)


print(
    "Effective research state: PASSED"
)


#
# TEST 4 - RESEARCH PROGRESS
#

print()
print("TEST 4 - RESEARCH PROGRESS")
print("--------------------------")


message = (
    ControlService._research_status_message(
        make_status(
            status="researching",
            total_questions=5,
            pending_questions=1,
            researching_questions=1,
            researched_questions=3,
        )
    )
)

assert (
    message
    ==
    "Research is in progress. "
    "3 of 5 questions have been researched."
)

print("Research progress message: PASSED")


#
# TEST 5 - RESEARCH PROGRESS AFTER SOME
#          QUESTIONS ENTER REVIEW
#

print()
print("TEST 5 - ADVANCED RESEARCH PROGRESS")
print("-----------------------------------")


message = (
    ControlService._research_status_message(
        make_status(
            status="researching",
            total_questions=6,
            pending_questions=1,
            researching_questions=1,
            researched_questions=1,
            reviewing_questions=1,
            reviewed_questions=2,
        )
    )
)

assert (
    message
    ==
    "Research is in progress. "
    "4 of 6 questions have been researched."
)

print(
    "Advanced research progress: PASSED"
)


#
# TEST 6 - REVIEW PROGRESS
#

print()
print("TEST 6 - REVIEW PROGRESS")
print("------------------------")


message = (
    ControlService._research_status_message(
        make_status(
            status="reviewing",
            total_questions=5,
            researched_questions=1,
            reviewing_questions=1,
            reviewed_questions=3,
        )
    )
)

assert (
    message
    ==
    "Research review is in progress. "
    "3 of 5 questions have been reviewed."
)

print("Review progress message: PASSED")


#
# TEST 7 - REPORT PERSISTED BEFORE COMPLETION
#

print()
print("TEST 7 - REPORT PERSISTED")
print("-------------------------")


message = (
    ControlService._research_status_message(
        make_status(
            status="reporting",
            total_questions=5,
            reviewed_questions=5,
            report_available=True,
        )
    )
)

assert (
    message
    ==
    "The research report has been generated "
    "and is awaiting workflow completion."
)

print("Persisted report message: PASSED")


#
# TEST 8 - COMPLETED
#

print()
print("TEST 8 - COMPLETED")
print("------------------")


message = (
    ControlService._research_status_message(
        make_status(
            status="completed",
            total_questions=5,
            reviewed_questions=5,
            report_available=True,
        )
    )
)

assert (
    message
    ==
    "Research is complete and the "
    "report is available."
)

print("Completion message: PASSED")


#
# TEST 9 - UNKNOWN STATUS
#

print()
print("TEST 9 - UNKNOWN STATUS")
print("-----------------------")


message = (
    ControlService._research_status_message(
        make_status(
            status="future_status",
        )
    )
)

assert (
    message
    ==
    "Research session status: future_status."
)

print("Unknown status fallback: PASSED")


print()
print("===========================")
print("PASS")
print("===========================")

print(
    "Control status messages now describe "
    "durable research progress and cooperative "
    "pause state."
)