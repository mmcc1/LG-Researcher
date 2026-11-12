from control.add_question_command_handler import (
    AddQuestionCommandHandler,
)

from domain.control import (
    ControlCommand,
    ControlContext,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


#
# Create a small dedicated session.
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = repository.create(
        topic="Control Agent add-question test"
    )

    repository.set_status(
        research_session.id,
        "planned",
    )

    session_id = (
        research_session.id
    )


print()
print(
    "ADD QUESTION HANDLER TEST"
)
print(
    "========================="
)

print(
    f"Session: {session_id}"
)


handler = AddQuestionCommandHandler(
    session_factory=SessionLocal,
)


context = ControlContext(
    session_id=session_id,
    topic=(
        "Control Agent add-question test"
    ),
    status="planned",
)


command = ControlCommand(
    operation="add_question",
    question=(
        "Has SHA-256 ever suffered "
        "a practical collision attack?"
    ),
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


assert (
    result.session_id
    == session_id
)

assert (
    result.status
    == "pending"
)

assert (
    result.question
    == (
        "Has SHA-256 ever suffered "
        "a practical collision attack?"
    )
)


#
# Verify independently from SQL.
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    questions = (
        repository.get_questions(
            session_id
        )
    )


assert len(questions) == 1

assert (
    questions[0].id
    == result.question_id
)

assert (
    questions[0].status
    == "pending"
)


print()
print(
    "PASS: research question was "
    "persisted as pending."
)