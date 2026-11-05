from domain.control import ControlCommand, ControlContext
from processing.control_command_validator import ControlCommandValidator
from processing.control_lifecycle_policy import ControlLifecyclePolicy


validator = ControlCommandValidator()
policy = ControlLifecyclePolicy()


def context(status=None, session_id=None):
    return ControlContext(
        session_id=session_id,
        topic="Control rejection test" if session_id else None,
        status=status,
        pause_requested=False,
    )


def check_rejected(operation, ctx, expected_stage):
    command = ControlCommand(operation=operation)

    try:
        validated = validator.validate(command, ctx)
        policy.validate(validated, ctx)
    except ValueError:
        print(f"{operation} rejected at {expected_stage}: PASSED")
        return

    raise AssertionError(
        f"{operation} should have been rejected "
        f"for status={ctx.status!r}"
    )


def check_allowed(operation, ctx):
    command = ControlCommand(operation=operation)
    validated = validator.validate(command, ctx)
    policy.validate(validated, ctx)
    print(f"{operation} allowed for {ctx.status}: PASSED")


print()
print("CONTROL REJECTION POLICY TEST")
print("=============================")

check_rejected("pause", context(), "validator")
check_rejected("resume", context(), "validator")

check_rejected(
    "pause",
    context(status="completed", session_id="test-session"),
    "lifecycle policy",
)

check_rejected(
    "resume",
    context(status="completed", session_id="test-session"),
    "lifecycle policy",
)

check_rejected(
    "pause",
    context(status="created", session_id="test-session"),
    "lifecycle policy",
)

check_allowed(
    "resume",
    context(status="created", session_id="test-session"),
)

check_allowed(
    "status",
    context(status="completed", session_id="test-session"),
)

print()
print("=============================")
print("PASS")
print("=============================")