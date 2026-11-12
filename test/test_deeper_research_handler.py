from domain.control import (
    ControlCommand,
    ControlContext,
)

from control.deeper_research_command_handler import (
    DeeperResearchCommandHandler,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)


QUESTION_TEXT = (
    "What role does SHA-256 play "
    "in Bitcoin proof-of-work?"
)


print()
print(
    "DEEPER RESEARCH HANDLER TEST"
)
print(
    "============================"
)


#
# Create isolated test session.
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic=(
                "Synthetic deeper research test"
            )
        )
    )

    session_id = (
        research_session.id
    )

    repository.set_status(
        session_id,
        "planned",
    )

    question = (
        repository.add_question(
            session_id=session_id,
            question=QUESTION_TEXT,
        )
    )

    question_id = question.id

    repository.set_question_status(
        question_id,
        "researched",
    )

    repository.set_status(
        session_id,
        "researched",
    )


print(
    f"Session: {session_id}"
)

print(
    f"Question: {question_id}"
)


#
# Execute handler directly.
#

handler = (
    DeeperResearchCommandHandler(
        session_factory=SessionLocal,
    )
)

command = ControlCommand(
    operation="deeper_research",
    question=QUESTION_TEXT,
    instructions=(
        "Focus specifically on how "
        "double SHA-256 is used during "
        "block-header validation."
    ),
)

context = ControlContext(
    session_id=session_id,
    topic=(
        "Synthetic deeper research test"
    ),
    status="researched",
)

result = handler.execute(
    command=command,
    context=context,
)


print()
print(
    result.model_dump_json(
        indent=2
    )
)


#
# Verify durable state.
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    attempt_repository = (
        SearchAttemptRepository(db)
    )

    research_session = (
        session_repository.get(
            session_id
        )
    )

    question = (
        session_repository.get_question(
            question_id
        )
    )

    attempt = (
        attempt_repository.get(
            result.search_attempt_id
        )
    )

    assert research_session is not None
    assert question is not None
    assert attempt is not None

    assert (
        research_session.status
        == "researching"
    )

    assert (
        question.status
        == "pending"
    )

    assert (
        attempt.status
        == "pending"
    )

    assert (
        attempt.purpose
        == "deeper_research"
    )

    assert (
        attempt.research_question_id
        == question_id
    )

    assert (
        attempt.instructions
        == command.instructions
    )


print()
print(
    "============================"
)
print(
    "PASS"
)
print(
    "============================"
)
print(
    "Deeper research was scheduled "
    "without executing the research "
    "workflow."
)