"""Stage 7.20C: rejected control commands must not modify persisted state.

Set CREATED_SESSION_ID and COMPLETED_SESSION_ID to existing test sessions.

$env:CREATED_SESSION_ID = "your-created-session-id"
$env:COMPLETED_SESSION_ID = "your-completed-session-id"


$env:CREATED_SESSION_ID = "1e24e4c4-b16a-4304-b863-cd35e5afcd05"
$env:COMPLETED_SESSION_ID = "fae69e3e-58d2-4c6a-8ac1-85cf6994db06"

No LLM, graph execution, or SQL writes are performed by this test.
"""

import os
from sqlalchemy import inspect
from sqlalchemy.orm import class_mapper

from domain.control import ControlCommand
from control.control_service import ControlService
from control.control_context_factory import ControlContextFactory
from processing.control_command_validator import ControlCommandValidator
from processing.control_lifecycle_policy import ControlLifecyclePolicy
from persistence.database import SessionLocal
from persistence.models import ResearchSession
from persistence.research_session_repository import ResearchSessionRepository


class FixedControlAgent:
    def interpret(self, user_message, context):
        return ControlCommand(operation=user_message)


class ForbiddenHandler:
    def execute(self, *args, **kwargs):
        raise AssertionError("Rejected command reached a handler")


def snapshot(session_id):
    with SessionLocal() as db:
        repository = ResearchSessionRepository(db)
        session = repository.get(session_id)
        if session is None:
            raise AssertionError(f"Session not found: {session_id}")
        questions = repository.get_questions(session_id)
        session_fields = tuple(
            (column.key, getattr(session, column.key))
            for column in class_mapper(type(session)).columns
        )
        question_fields = tuple(
            tuple(
                (column.key, getattr(question, column.key))
                for column in class_mapper(type(question)).columns
            )
            for question in sorted(questions, key=lambda q: str(q.id))
        )
        return session_fields, question_fields


def assert_rejected(service, session_id, operation, expected_fragment):
    before = snapshot(session_id)
    try:
        service.execute(user_message=operation, session_id=session_id)
    except ValueError as exc:
        if expected_fragment not in str(exc):
            raise AssertionError(
                f"Unexpected rejection for {operation}: {exc}"
            ) from exc
    else:
        raise AssertionError(f"{operation} was unexpectedly accepted")
    after = snapshot(session_id)
    assert before == after, f"SQL changed after rejected {operation}"
    print(f"{operation} rejected; session and questions unchanged: PASSED")


def require_session(session_id, expected_status):
    with SessionLocal() as db:
        session = ResearchSessionRepository(db).get(session_id)
        assert session is not None, f"Session not found: {session_id}"
        assert session.status == expected_status, (
            f"Expected {expected_status!r}, got {session.status!r}"
        )


def main():
    created_id = os.environ.get("CREATED_SESSION_ID")
    completed_id = os.environ.get("COMPLETED_SESSION_ID")
    if not created_id or not completed_id:
        raise SystemExit(
            "Set CREATED_SESSION_ID and COMPLETED_SESSION_ID to existing "
            "disposable test sessions before running."
        )

    require_session(created_id, "created")
    require_session(completed_id, "completed")

    forbidden = ForbiddenHandler()
    service = ControlService(
        control_agent=FixedControlAgent(),
        context_factory=ControlContextFactory(SessionLocal),
        command_validator=ControlCommandValidator(),
        lifecycle_policy=ControlLifecyclePolicy(),
        status_handler=forbidden,
        help_handler=forbidden,
        start_research_handler=forbidden,
        resume_handler=forbidden,
        generate_report_handler=forbidden,
        add_question_handler=forbidden,
        modify_scope_handler=forbidden,
        deeper_research_handler=forbidden,
        counter_evidence_handler=forbidden,
        pause_handler=forbidden,
    )

    print("CONTROL SQL REJECTION INTEGRITY TEST")
    print("====================================")
    assert_rejected(service, completed_id, "pause", "cannot be paused")
    assert_rejected(service, completed_id, "resume", "cannot be resumed")
    assert_rejected(service, created_id, "pause", "cannot be paused")
    print("====================================")
    print("PASS")


if __name__ == "__main__":
    main()
