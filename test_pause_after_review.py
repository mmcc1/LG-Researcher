from nodes.complete_review import (
    CompleteReviewNode,
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

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


print()
print("AFTER-REVIEW PAUSE TEST")
print("=======================")


#
# -------------------------------------------------
# Arrange a session whose review work has
# completely finished.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    session = repository.create(
        topic="After-review pause test"
    )

    session_id = session.id

    repository.set_status(
        session_id,
        "reviewing",
    )

    question = repository.add_question(
        session_id=session_id,
        question=(
            "Can report generation be prevented "
            "from starting after review completes?"
        ),
        category="test",
        rationale=(
            "Verify the cooperative pause "
            "boundary between review and report."
        ),
    )

    repository.set_question_status(
        question_id=question.id,
        status="reviewed",
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
    "topic": "After-review pause test",
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
# Simulate a pause request arriving while the
# review phase is finishing.
#
# CompleteReviewNode must still be allowed to
# commit the durable phase transition.
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
# Complete the review phase.
# -------------------------------------------------
#

print()
print("TEST 1 - REVIEW PHASE COMPLETES")
print("-------------------------------")


complete_review = (
    CompleteReviewNode(
        SessionLocal
    )
)

complete_review(
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

    completed_question = (
        repository.get_question(
            question_id
        )
    )


assert completed_session is not None
assert completed_question is not None


assert (
    completed_session.status
    == "reviewed"
)

print(
    "Session status is reviewed: PASSED"
)


assert (
    completed_question.status
    == "reviewed"
)

print(
    "Question remains reviewed: PASSED"
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
# Verify the durable phase boundary.
#
# Report generation is downstream of this pause
# check and has not been invoked by this test.
# -------------------------------------------------
#

print()
print("TEST 3 - REPORT NOT STARTED")
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
    == "reviewed"
)

print(
    "Session remains reviewed: PASSED"
)


assert (
    paused_question.status
    == "reviewed"
)

print(
    "Question remains reviewed: PASSED"
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
# Simulate ResumeCommandHandler clearing the
# cooperative pause before workflow invocation.
# -------------------------------------------------
#

print()
print("TEST 4 - PREPARE REPORT RESUME")
print("------------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.clear_pause_request(
        session_id
    )


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
    "Pause request cleared: PASSED"
)


assert (
    resumed_session.status
    == "reviewed"
)

print(
    "Session remains reviewed: PASSED"
)


assert (
    resumed_question.status
    == "reviewed"
)

print(
    "Completed review remains reviewed: PASSED"
)


print()
print("=======================")
print("PASS")
print("=======================")

print(
    "The review phase completed durably, "
    "the pause boundary prevented report "
    "generation from starting, and the "
    "session remains ready to resume into "
    "the report phase."
)