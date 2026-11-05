from control.resume_command_handler import (
    ResumeCommandHandler,
)

from domain.control import (
    ControlContext,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


print()
print("PAUSE RESUME HANDLER TEST")
print("=========================")


#
# -------------------------------------------------
# Fake workflow result.
# -------------------------------------------------
#

class FakeWorkflowResult:

    def __init__(
        self,
        session_id: str,
    ):
        self.session_id = session_id


#
# -------------------------------------------------
# Fake workflow service.
#
# This verifies that the pause request has already
# been cleared BEFORE workflow execution begins.
# -------------------------------------------------
#

class FakeWorkflowService:

    def __init__(
        self,
        session_factory,
    ):
        self.session_factory = (
            session_factory
        )

        self.resume_called = False

    def resume(
        self,
        session_id: str,
    ):

        self.resume_called = True

        with self.session_factory() as db:

            repository = (
                ResearchSessionRepository(db)
            )

            research_session = (
                repository.get(
                    session_id
                )
            )

            assert (
                research_session
                is not None
            )

            assert (
                research_session.pause_requested
                is False
            )

            #
            # Resume must not alter the durable
            # lifecycle phase before the workflow
            # itself runs.
            #

            assert (
                research_session.status
                == "researching"
            )

        return FakeWorkflowResult(
            session_id=session_id,
        )


#
# -------------------------------------------------
# Create a suspended research session.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic="Pause resume handler test",
        )
    )

    session_id = (
        research_session.id
    )

    repository.set_status(
        session_id,
        "researching",
    )

    repository.request_pause(
        session_id
    )


print(
    f"Session ID: {session_id}"
)


#
# -------------------------------------------------
# Verify precondition.
# -------------------------------------------------
#

print()
print("TEST 1 - PRECONDITION")
print("---------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.get(
            session_id
        )
    )

    assert (
        research_session
        is not None
    )

    assert (
        research_session.status
        == "researching"
    )

    assert (
        research_session.pause_requested
        is True
    )


print(
    "Status is researching: PASSED"
)

print(
    "Pause request is True: PASSED"
)


#
# -------------------------------------------------
# Execute resume.
# -------------------------------------------------
#

print()
print("TEST 2 - RESUME")
print("---------------")


workflow_service = (
    FakeWorkflowService(
        session_factory=SessionLocal,
    )
)

handler = ResumeCommandHandler(
    workflow_service=workflow_service,
    session_factory=SessionLocal,
)

context = ControlContext(
    session_id=session_id,
    topic="Pause resume handler test",
    scope=None,
    status="researching",
)


result = handler.execute(
    context=context,
)


assert (
    workflow_service.resume_called
    is True
)

assert (
    result.session_id
    == session_id
)

assert (
    result.status
    == "researching"
)


print(
    "Workflow resume called: PASSED"
)

print(
    "Lifecycle phase preserved: PASSED"
)


#
# -------------------------------------------------
# Verify durable postcondition.
# -------------------------------------------------
#

print()
print("TEST 3 - DURABLE CLEAR")
print("----------------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.get(
            session_id
        )
    )

    assert (
        research_session
        is not None
    )

    assert (
        research_session.pause_requested
        is False
    )

    assert (
        research_session.status
        == "researching"
    )


print(
    "Pause request durably cleared: PASSED"
)

print(
    "Lifecycle status unchanged: PASSED"
)


print()
print("=========================")
print("PASS")
print("=========================")

print(
    "Resume clears cooperative pause before "
    "workflow execution and preserves the "
    "durable lifecycle phase."
)