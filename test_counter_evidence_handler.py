from control.counter_evidence_command_handler import (
    CounterEvidenceCommandHandler,
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

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)


print()
print(
    "COUNTER-EVIDENCE HANDLER TEST"
)
print(
    "============================="
)


#
# -------------------------------------------------
# Create a fresh synthetic research session.
# -------------------------------------------------
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        session_repository.create(
            topic=(
                "Bitcoin proof-of-work hashing"
            )
        )
    )

    session_id = (
        research_session.id
    )


#
# -------------------------------------------------
# Add one question.
# -------------------------------------------------
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    question = (
        session_repository.add_question(
            session_id=session_id,
            question=(
                "What role does SHA-256 play "
                "in Bitcoin proof-of-work?"
            ),
            category="technical",
            rationale=(
                "Establish how SHA-256 is used "
                "within Bitcoin proof-of-work."
            ),
        )
    )

    question_id = question.id
    question_text = question.question


#
# -------------------------------------------------
# Put the synthetic data into the lifecycle state
# required for counter-evidence:
#
#     session = researched
#     question = researched
#
# No actual research is required for this boundary
# test because we are testing scheduling only.
# -------------------------------------------------
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    session_repository.set_question_status(
        question_id=question_id,
        status="researched",
    )

    session_repository.set_status(
        session_id=session_id,
        status="researched",
    )


print()
print("INITIAL STATE")
print("-------------")

print(
    f"Session ID: "
    f"{session_id}"
)

print(
    f"Question ID: "
    f"{question_id}"
)

print(
    f"Question: "
    f"{question_text}"
)

print(
    "Session status: researched"
)

print(
    "Question status: researched"
)


#
# -------------------------------------------------
# Build the trusted control inputs.
# -------------------------------------------------
#

context = ControlContext(
    session_id=session_id,
    topic=(
        "Bitcoin proof-of-work hashing"
    ),
    status="researched",
)

command = ControlCommand(
    operation="counter_evidence",
    question=question_text,
    instructions=(
        "Look specifically for credible "
        "technical evidence that challenges, "
        "qualifies, or limits common claims "
        "about the security role of SHA-256 "
        "in Bitcoin proof-of-work."
    ),
)


#
# -------------------------------------------------
# Execute the real handler.
# -------------------------------------------------
#

handler = CounterEvidenceCommandHandler(
    session_factory=SessionLocal,
)


print()
print(
    "Scheduling counter-evidence..."
)

result = handler.execute(
    command=command,
    context=context,
)


print()
print("HANDLER RESULT")
print("--------------")

print(
    f"SearchAttempt ID: "
    f"{result.search_attempt_id}"
)

print(
    f"Session ID: "
    f"{result.session_id}"
)

print(
    f"Question ID: "
    f"{result.question_id}"
)

print(
    f"Question: "
    f"{result.question}"
)

print(
    f"Instructions: "
    f"{result.instructions}"
)

print(
    f"Status: "
    f"{result.status}"
)


#
# -------------------------------------------------
# Verify the SearchAttempt independently from SQL.
# -------------------------------------------------
#

with SessionLocal() as db:

    attempt_repository = (
        SearchAttemptRepository(db)
    )

    attempt = (
        attempt_repository.get(
            result.search_attempt_id
        )
    )

    assert attempt is not None

    print()
    print("PERSISTED SEARCH ATTEMPT")
    print("------------------------")

    print(
        f"Attempt ID: "
        f"{attempt.id}"
    )

    print(
        f"Purpose: "
        f"{attempt.purpose}"
    )

    print(
        f"Status: "
        f"{attempt.status}"
    )

    print(
        f"Instructions: "
        f"{attempt.instructions}"
    )

    assert (
        attempt.research_session_id
        == session_id
    )

    assert (
        attempt.research_question_id
        == question_id
    )

    assert (
        attempt.purpose
        == "counter_evidence"
    )

    assert (
        attempt.status
        == "pending"
    )

    assert (
        attempt.instructions
        == command.instructions
    )


#
# -------------------------------------------------
# Verify that the question and session were reopened
# as part of the same scheduling operation.
# -------------------------------------------------
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
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

    assert research_session is not None
    assert question is not None

    print()
    print("PERSISTED WORKFLOW STATE")
    print("------------------------")

    print(
        f"Session status: "
        f"{research_session.status}"
    )

    print(
        f"Question status: "
        f"{question.status}"
    )

    assert (
        research_session.status
        == "researching"
    )

    assert (
        question.status
        == "pending"
    )


#
# -------------------------------------------------
# Verify the returned result agrees with the durable
# state.
# -------------------------------------------------
#

assert (
    result.search_attempt_id
    == attempt.id
)

assert (
    result.session_id
    == session_id
)

assert (
    result.question_id
    == question_id
)

assert (
    result.question
    == question_text
)

assert (
    result.status
    == "pending"
)


print()
print(
    "============================="
)
print("PASS")
print(
    "============================="
)
print(
    "Counter-evidence was scheduled "
    "as a durable SearchAttempt."
)
print(
    "The target question was reopened "
    "and the session returned to research."
)