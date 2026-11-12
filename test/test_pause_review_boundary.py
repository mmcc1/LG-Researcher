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
print("REVIEW PAUSE BOUNDARY TEST")
print("==========================")


#
# -------------------------------------------------
# Arrange a session with:
#
# question 1 = current review
# question 2 = waiting for review
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    session = repository.create(
        topic="Review pause boundary test"
    )

    session_id = session.id

    repository.set_status(
        session_id,
        "reviewing",
    )

    question_1 = repository.add_question(
        session_id=session_id,
        question=(
            "What happens to the review "
            "that completes before a pause?"
        ),
        category="test",
        rationale=(
            "Verify completed reviews are "
            "not replayed after suspension."
        ),
    )

    question_2 = repository.add_question(
        session_id=session_id,
        question=(
            "Does the next review remain "
            "unstarted while paused?"
        ),
        category="test",
        rationale=(
            "Verify the next review does not "
            "cross the cooperative boundary."
        ),
    )

    repository.set_question_status(
        question_id=question_1.id,
        status="reviewing",
    )

    repository.set_question_status(
        question_id=question_2.id,
        status="researched",
    )

    question_1_id = question_1.id
    question_2_id = question_2.id


print(
    f"Session ID: {session_id}"
)

print(
    f"Current review question: "
    f"{question_1_id}"
)

print(
    f"Next review question: "
    f"{question_2_id}"
)


state = {
    "session_id": session_id,
    "topic": "Review pause boundary test",
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
    "current_review_question_id": (
        question_1_id
    ),
    "current_review_question": (
        "What happens to the review "
        "that completes before a pause?"
    ),
}


#
# -------------------------------------------------
# Simulate successful durable completion of the
# current ReviewQuestionNode.
#
# ReviewQuestionNode itself guarantees that it
# only sets this status after a durable review
# exists. This boundary test is concerned with
# what happens after that transition.
# -------------------------------------------------
#

print()
print("TEST 1 - CURRENT REVIEW COMPLETES")
print("---------------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.set_question_status(
        question_id=question_1_id,
        status="reviewed",
    )


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    completed_question = (
        repository.get_question(
            question_1_id
        )
    )


assert completed_question is not None

assert (
    completed_question.status
    == "reviewed"
)

print(
    "Current question is reviewed: PASSED"
)


#
# -------------------------------------------------
# Pause arrives during/currently around completion.
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
# Execute the real pause boundary.
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
# Verify next review has NOT started.
# -------------------------------------------------
#

print()
print("TEST 3 - NEXT REVIEW NOT STARTED")
print("--------------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    paused_session = (
        repository.get(
            session_id
        )
    )

    first_question = (
        repository.get_question(
            question_1_id
        )
    )

    second_question = (
        repository.get_question(
            question_2_id
        )
    )


assert paused_session is not None
assert first_question is not None
assert second_question is not None


assert (
    paused_session.status
    == "reviewing"
)

print(
    "Session remains reviewing: PASSED"
)


assert (
    first_question.status
    == "reviewed"
)

print(
    "Completed review remains reviewed: PASSED"
)


assert (
    second_question.status
    == "researched"
)

print(
    "Next question remains researched: PASSED"
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
# -------------------------------------------------
#

print()
print("TEST 4 - RESUME NEXT REVIEW")
print("---------------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.clear_pause_request(
        session_id
    )


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


#
# The completed review must NOT be selected again.
#

assert (
    state[
        "current_review_question_id"
    ]
    == question_2_id
)

print(
    "Next question selected: PASSED"
)

assert (
    state[
        "current_review_question_id"
    ]
    != question_1_id
)

print(
    "Completed review not replayed: PASSED"
)


#
# -------------------------------------------------
# Verify durable resumed state.
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

    first_question = (
        repository.get_question(
            question_1_id
        )
    )

    second_question = (
        repository.get_question(
            question_2_id
        )
    )


assert resumed_session is not None
assert first_question is not None
assert second_question is not None


assert (
    resumed_session.pause_requested
    is False
)

print(
    "Pause request remains cleared: PASSED"
)


assert (
    first_question.status
    == "reviewed"
)

print(
    "First question remains reviewed: PASSED"
)


assert (
    second_question.status
    == "reviewing"
)

print(
    "Second question transitioned "
    "researched -> reviewing: PASSED"
)


assert (
    resumed_session.status
    == "reviewing"
)

print(
    "Session remains in review phase: PASSED"
)


print()
print("==========================")
print("PASS")
print("==========================")

print(
    "The completed review remained durable, "
    "the pause prevented the next review "
    "from starting, and resume selected only "
    "the remaining review work."
)