from nodes.complete_research import (
    CompleteResearchNode,
)

from nodes.check_pause import (
    CheckPauseNode,
)

from nodes.select_review_question import (
    SelectReviewQuestionNode,
)

from graph.research_graph import (
    route_pause,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


print()
print("AFTER-RESEARCH PAUSE TEST")
print("=========================")


#
# -------------------------------------------------
# Arrange a session whose research questions have
# all completed.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    session = repository.create(
        topic="After-research pause test"
    )

    session_id = session.id

    repository.set_status(
        session_id,
        "researching",
    )

    question = repository.add_question(
        session_id=session_id,
        question=(
            "Can review be prevented from "
            "starting after research completes?"
        ),
        category="test",
        rationale=(
            "Verify the cooperative pause "
            "boundary between research "
            "and review."
        ),
    )

    repository.set_question_status(
        question_id=question.id,
        status="researched",
    )

    question_id = question.id


print(
    f"Session ID: {session_id}"
)

print(
    f"Question ID: {question_id}"
)


state = {
    "session_id": session_id,
    "topic": "After-research pause test",
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
# Simulate the pause arriving immediately before
# overall research completion.
#
# CompleteResearchNode must still be allowed to
# commit the phase completion.
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
# Complete the research phase.
# -------------------------------------------------
#

print()
print("TEST 1 - RESEARCH PHASE COMPLETES")
print("---------------------------------")


complete_research = (
    CompleteResearchNode(
        SessionLocal
    )
)

complete_research(
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
    == "researched"
)

print(
    "Session status is researched: PASSED"
)


#
# -------------------------------------------------
# Check the durable pause flag at the real
# production boundary.
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
# Verify review has NOT begun.
# -------------------------------------------------
#

print()
print("TEST 3 - REVIEW NOT STARTED")
print("---------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    paused_session = (
        repository.get(
            session_id
        )
    )

    paused_question = (
        repository.get_question(
            question_id
        )
    )


assert paused_session is not None
assert paused_question is not None


assert (
    paused_session.status
    == "researched"
)

print(
    "Session remains researched: PASSED"
)


assert (
    paused_question.status
    == "researched"
)

print(
    "Question remains researched: PASSED"
)


assert (
    paused_session.pause_requested
    is True
)

print(
    "Pause request remains durable: PASSED"
)


#
# -------------------------------------------------
# Resume.
#
# ResumeCommandHandler normally clears the pause
# request before invoking the workflow.
# -------------------------------------------------
#

print()
print("TEST 4 - RESUME INTO REVIEW")
print("---------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.clear_pause_request(
        session_id
    )


#
# This is the production node reached when a
# researched session resumes into the review
# phase.
#

select_review_question = (
    SelectReviewQuestionNode(
        SessionLocal
    )
)

selection_update = (
    select_review_question(
        state
    )
)

state.update(
    selection_update
)


assert (
    state[
        "current_review_question_id"
    ]
    == question_id
)

print(
    "Research question selected "
    "for review: PASSED"
)


#
# -------------------------------------------------
# Verify durable review state.
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

    resumed_question = (
        repository.get_question(
            question_id
        )
    )


assert resumed_session is not None
assert resumed_question is not None


assert (
    resumed_session.pause_requested
    is False
)

print(
    "Pause request remains cleared: PASSED"
)


assert (
    resumed_session.status
    == "reviewing"
)

print(
    "Session transitioned "
    "researched -> reviewing: PASSED"
)


assert (
    resumed_question.status
    == "reviewing"
)

print(
    "Question transitioned "
    "researched -> reviewing: PASSED"
)


print()
print("=========================")
print("PASS")
print("=========================")

print(
    "The research phase completed durably, "
    "the workflow stopped before review "
    "started, and resume entered review "
    "without replaying research."
)