from nodes.complete_question import (
    CompleteQuestionNode,
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
print("RESEARCH PAUSE BOUNDARY TEST")
print("============================")


#
# -------------------------------------------------
# Arrange a durable research session.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    session = repository.create(
        topic="Research pause boundary test"
    )

    session_id = session.id

    repository.set_status(
        session_id,
        "researching",
    )

    question = repository.add_question(
        session_id=session_id,
        question=(
            "Can a completed research question "
            "stop safely at the pause boundary?"
        ),
        category="test",
        rationale=(
            "Verify cooperative pause after "
            "question completion."
        ),
    )

    repository.set_question_status(
        question_id=question.id,
        status="researching",
    )

    question_id = question.id


print(
    f"Session ID: {session_id}"
)

print(
    f"Question ID: {question_id}"
)


#
# -------------------------------------------------
# Simulate a pause arriving while the current
# research unit is executing.
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
# The graph state represents the current research
# unit immediately before CompleteQuestionNode.
#

state = {
    "session_id": session_id,
    "topic": (
        "Research pause boundary test"
    ),
    "scope": None,
    "resume": False,
    "resume_phase": None,
    "execution_target": "complete",
    "pause_requested": False,
    "research_plan": None,
    "current_question_id": question_id,
    "current_question": (
        "Can a completed research question "
        "stop safely at the pause boundary?"
    ),
    "search_required": False,
    "current_search_attempt_id": None,
    "search_plan": None,
    "search_results": [],
    "current_review_question_id": None,
    "current_review_question": None,
}


#
# -------------------------------------------------
# Complete the current unit of work.
# -------------------------------------------------
#

print()
print("TEST 1 - CURRENT QUESTION COMPLETES")
print("-----------------------------------")


complete_question = (
    CompleteQuestionNode(
        SessionLocal
    )
)

complete_question(
    state
)


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    completed_question = (
        repository.get_question(
            question_id
        )
    )


assert completed_question is not None

assert (
    completed_question.status
    == "researched"
)


print(
    "Question status is researched: PASSED"
)


#
# -------------------------------------------------
# Execute the real production pause check.
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

pause_update = check_pause(
    state
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


#
# -------------------------------------------------
# Execute the same router used by the production
# graph.
# -------------------------------------------------
#

print()
print("TEST 3 - ROUTING")
print("----------------")


route = route_pause(
    state
)

assert route == "pause"

print(
    "Pause route selected: PASSED"
)


#
# -------------------------------------------------
# Verify the overall session has NOT advanced to
# researched yet.
#
# CompleteResearchNode is downstream of another
# SelectQuestionNode and therefore must not have
# executed after this pause boundary.
# -------------------------------------------------
#

print()
print("TEST 4 - PHASE NOT ADVANCED")
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


assert paused_session is not None

assert (
    paused_session.status
    == "researching"
)

print(
    "Session remains researching: PASSED"
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
# Resume from the durable research boundary.
# -------------------------------------------------
#

print()
print("TEST 5 - RESUME AFTER LAST QUESTION")
print("-----------------------------------")


#
# ResumeCommandHandler normally performs this
# before invoking the workflow.
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    repository.clear_pause_request(
        session_id
    )


#
# Reproduce the production research-resume path:
#
# researching
#     -> SelectQuestionNode
#     -> no active question
#     -> no pending question
#     -> CompleteResearchNode
#     -> researched
#
# No LLM or external work is required.
#

from nodes.select_question import (
    SelectQuestionNode,
)

from nodes.complete_research import (
    CompleteResearchNode,
)


select_question = (
    SelectQuestionNode(
        SessionLocal
    )
)

selection_update = (
    select_question(
        state
    )
)

state.update(
    selection_update
)


assert (
    state["current_question_id"]
    is None
)

print(
    "No research question replayed: PASSED"
)


complete_research = (
    CompleteResearchNode(
        SessionLocal
    )
)

complete_research(
    state
)


#
# -------------------------------------------------
# Verify final durable research state.
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
    resumed_question.status
    == "researched"
)

print(
    "Completed question remains researched: PASSED"
)


assert (
    resumed_session.status
    == "researched"
)

print(
    "Session advanced to researched: PASSED"
)

print()
print("============================")
print("PASS")
print("============================")

print(
    "The research workflow stopped safely "
    "after the current question completed, "
    "preserved its durable state, and resumed "
    "without replaying completed research."
)