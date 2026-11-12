from domain.report import (
    ResearchReport,
)

from nodes.generate_report import (
    GenerateReportNode,
)

from nodes.complete_report import (
    CompleteReportNode,
)

from nodes.check_pause import (
    CheckPauseNode,
)

from graph.research_graph import (
    route_pause,
)

from persistence.database import (
    SessionLocal,
)

from persistence.report_repository import (
    ReportRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


print()
print("REPORT PAUSE BOUNDARY TEST")
print("==========================")


#
# -------------------------------------------------
# Arrange a session at the reporting phase.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    session = repository.create(
        topic="Report pause boundary test"
    )

    session_id = session.id

    repository.set_status(
        session_id,
        "reporting",
    )


print(
    f"Session ID: {session_id}"
)


state = {
    "session_id": session_id,
    "topic": "Report pause boundary test",
    "scope": None,
    "resume": False,
    "resume_phase": None,
    "execution_target": "complete",
    "pause_requested": False,
    "research_plan": None,
    "current_question_id": None,
    "current_question": None,
    "search_required": False,
    "current_search_attempt_id": None,
    "search_plan": None,
    "search_results": [],
    "current_review_question_id": None,
    "current_review_question": None,
}


#
# -------------------------------------------------
# Persist the report.
#
# This represents the durable output of
# GenerateReportNode immediately before
# check_pause_report.
# -------------------------------------------------
#

print()
print("TEST 1 - REPORT IS DURABLE")
print("--------------------------")


report = ResearchReport(
    title="Report Pause Boundary Test",
    executive_summary=(
        "A deterministic report used to test "
        "the cooperative pause boundary."
    ),
    sections=[],
    conclusions=(
        "The persisted report represents "
        "completed report-generation work."
    ),
    limitations=[],
)


with SessionLocal() as db:

    repository = (
        ReportRepository(db)
    )

    repository.save(
        session_id=session_id,
        report=report,
    )


with SessionLocal() as db:

    repository = (
        ReportRepository(db)
    )

    assert repository.exists_for_session(
        session_id
    )


print(
    "Report persisted: PASSED"
)


#
# -------------------------------------------------
# Request pause after report generation has
# completed but before CompleteReportNode.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.request_pause(
        session_id
    )


#
# -------------------------------------------------
# Execute the production pause check.
# -------------------------------------------------
#

print()
print("TEST 2 - PAUSE OBSERVED")
print("-----------------------")


check_pause = (
    CheckPauseNode(
        SessionLocal
    )
)

pause_update = (
    check_pause(
        state
    )
)

state.update(
    pause_update
)


assert (
    state["pause_requested"]
    is True
)

print(
    "Pause check returned True: PASSED"
)


route = route_pause(
    state
)

assert route == "pause"

print(
    "Pause route selected: PASSED"
)


#
# -------------------------------------------------
# CompleteReportNode must NOT have executed.
# -------------------------------------------------
#

print()
print("TEST 3 - SESSION NOT COMPLETED")
print("------------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    paused_session = (
        repository.get(
            session_id
        )
    )


assert paused_session is not None


assert (
    paused_session.status
    == "reporting"
)

print(
    "Session remains reporting: PASSED"
)


assert (
    paused_session.pause_requested
    is True
)

print(
    "Pause request remains durable: PASSED"
)


with SessionLocal() as db:

    repository = (
        ReportRepository(db)
    )

    assert repository.exists_for_session(
        session_id
    )


print(
    "Report remains durable: PASSED"
)


#
# -------------------------------------------------
# Resume.
#
# ResumeCommandHandler normally clears this before
# invoking the workflow.
# -------------------------------------------------
#

print()
print("TEST 4 - RESUME REPORT")
print("----------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.clear_pause_request(
        session_id
    )


#
# -------------------------------------------------
# Exercise GenerateReportNode's real recovery path.
#
# The report already exists, so this must return
# before:
#
#   - integrity checks
#   - status changes
#   - context construction
#   - Report Agent invocation
#
# We therefore supply fail-fast dependencies. If
# any of them are touched, the test fails.
# -------------------------------------------------
#

class FailIfCalled:

    def __getattr__(
        self,
        name,
    ):
        raise AssertionError(
            "Report generation dependency "
            f"was unexpectedly accessed: {name}"
        )


generate_report = (
    GenerateReportNode(
        session_factory=SessionLocal,
        report_agent=FailIfCalled(),
        context_builder=FailIfCalled(),
        validator=FailIfCalled(),
    )
)


generate_report(
    state
)


print(
    "Existing report detected: PASSED"
)

print(
    "Report Agent not replayed: PASSED"
)


#
# -------------------------------------------------
# The session should still be reporting until
# CompleteReportNode executes.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    resumed_session = (
        repository.get(
            session_id
        )
    )


assert resumed_session is not None


assert (
    resumed_session.status
    == "reporting"
)

print(
    "Session remains reporting before "
    "completion: PASSED"
)


assert (
    resumed_session.pause_requested
    is False
)

print(
    "Pause request remains cleared: PASSED"
)


#
# -------------------------------------------------
# Complete the session.
# -------------------------------------------------
#

print()
print("TEST 5 - COMPLETE REPORT")
print("------------------------")


complete_report = (
    CompleteReportNode(
        SessionLocal
    )
)

complete_report(
    state
)


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    completed_session = (
        repository.get(
            session_id
        )
    )


assert completed_session is not None


assert (
    completed_session.status
    == "completed"
)

print(
    "Session transitioned "
    "reporting -> completed: PASSED"
)


assert (
    completed_session.pause_requested
    is False
)

print(
    "Pause request remains cleared: PASSED"
)


#
# The report must still exist after completion.
#

with SessionLocal() as db:

    repository = (
        ReportRepository(db)
    )

    assert repository.exists_for_session(
        session_id
    )


print(
    "Persisted report retained: PASSED"
)


print()
print("==========================")
print("PASS")
print("==========================")

print(
    "The report remained durable across the "
    "cooperative pause, resume skipped report "
    "regeneration, and the session completed "
    "without replaying the Report Agent."
)