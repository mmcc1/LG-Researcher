from domain.control import (
    ControlCommand,
    ControlContext,
)

from processing.control_command_validator import (
    ControlCommandValidator,
)

from processing.control_lifecycle_policy import (
    ControlLifecyclePolicy,
)


print()
print("MODIFY SCOPE CONTROL POLICY TEST")
print("================================")


validator = ControlCommandValidator()
policy = ControlLifecyclePolicy()


#
# -------------------------------------------------
# TEST 1
# Valid scope command is canonicalised.
# -------------------------------------------------
#

print()
print("TEST 1 - COMMAND CANONICALISATION")
print("---------------------------------")


context = ControlContext(
    session_id="test-session",
    topic="Bitcoin",
    scope="Existing scope",
    status="researching",
)


raw_command = ControlCommand(
    operation="modify_scope",
    topic="This must be removed",
    question="This must also be removed",
    scope=(
        "Focus on mining economics "
        "and energy markets."
    ),
    instructions=(
        "This must also be removed."
    ),
)


command = validator.validate(
    command=raw_command,
    context=context,
)


assert command.operation == "modify_scope"

assert command.scope == (
    "Focus on mining economics "
    "and energy markets."
)

assert command.topic is None
assert command.question is None
assert command.instructions is None


print(
    "modify_scope canonicalisation: PASSED"
)


#
# -------------------------------------------------
# TEST 2
# researching is allowed.
# -------------------------------------------------
#

print()
print("TEST 2 - RESEARCHING ALLOWED")
print("----------------------------")


policy.validate(
    command=command,
    context=context,
)


print(
    "researching lifecycle: PASSED"
)


#
# -------------------------------------------------
# TEST 3
# researched is allowed.
# -------------------------------------------------
#

print()
print("TEST 3 - RESEARCHED ALLOWED")
print("---------------------------")


policy.validate(
    command=command,
    context=ControlContext(
        session_id="test-session",
        topic="Bitcoin",
        scope="Existing scope",
        status="researched",
    ),
)


print(
    "researched lifecycle: PASSED"
)


#
# -------------------------------------------------
# TEST 4
# review and completed states are rejected.
# -------------------------------------------------
#

print()
print("TEST 4 - LATE STATES REJECTED")
print("-----------------------------")


rejected_statuses = [
    "reviewing",
    "reviewed",
    "reporting",
    "completed",
]


for status in rejected_statuses:

    try:

        policy.validate(
            command=command,
            context=ControlContext(
                session_id="test-session",
                topic="Bitcoin",
                scope="Existing scope",
                status=status,
            ),
        )

        raise AssertionError(
            f"Status '{status}' was not rejected."
        )

    except ValueError:

        pass


print(
    "late lifecycle rejection: PASSED"
)


#
# -------------------------------------------------
# TEST 5
# planned is deliberately rejected for now.
# -------------------------------------------------
#

print()
print("TEST 5 - PLANNED REJECTED")
print("-------------------------")


try:

    policy.validate(
        command=command,
        context=ControlContext(
            session_id="test-session",
            topic="Bitcoin",
            scope=None,
            status="planned",
        ),
    )

    raise AssertionError(
        "planned session accepted scope change."
    )

except ValueError:

    pass


print(
    "planned lifecycle rejection: PASSED"
)


#
# -------------------------------------------------
# TEST 6
# Missing/empty scope is rejected.
# -------------------------------------------------
#

print()
print("TEST 6 - SCOPE REQUIRED")
print("-----------------------")


for invalid_scope in [
    None,
    "",
    "   ",
]:

    try:

        validator.validate(
            command=ControlCommand(
                operation="modify_scope",
                scope=invalid_scope,
            ),
            context=context,
        )

        raise AssertionError(
            "Invalid scope was accepted."
        )

    except ValueError:

        pass


print(
    "scope requirement: PASSED"
)


#
# -------------------------------------------------
# TEST 7
# Active session is required.
# -------------------------------------------------
#

print()
print("TEST 7 - SESSION REQUIRED")
print("-------------------------")


try:

    validator.validate(
        command=ControlCommand(
            operation="modify_scope",
            scope="Some scope",
        ),
        context=ControlContext(
            session_id=None,
            topic=None,
            scope=None,
            status=None,
        ),
    )

    raise AssertionError(
        "modify_scope accepted without "
        "an active session."
    )

except ValueError:

    pass


print(
    "active session requirement: PASSED"
)


print()
print("================================")
print("PASS")
print("================================")
print(
    "Modify-scope command and lifecycle "
    "policy behave as expected."
)