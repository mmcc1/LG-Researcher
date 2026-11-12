from domain.control import (
    ControlCommand,
    ControlContext,
)

from processing.control_command_validator import (
    ControlCommandValidator,
)


print()
print("INITIAL RESEARCH SCOPE TEST")
print("===========================")


validator = ControlCommandValidator()

context = ControlContext(
    session_id=None,
    topic=None,
    scope=None,
    status=None,
)


#
# -------------------------------------------------
# TEST 1
#
# start_research with an initial persistent scope.
# -------------------------------------------------
#

print()
print("TEST 1 - INITIAL SCOPE")
print("----------------------")


topic = (
    "The effect of Bitcoin mining "
    "on energy systems"
)

scope = (
    "Focus specifically on electricity pricing, "
    "grid incentives, and renewable-energy "
    "investment."
)


command = ControlCommand(
    operation="start_research",
    topic=topic,
    scope=scope,
)


validated = validator.validate(
    command=command,
    context=context,
)


assert (
    validated.operation
    == "start_research"
)

assert (
    validated.topic
    == topic
)

assert (
    validated.scope
    == scope
)

assert (
    validated.question
    is None
)


print(
    "Initial scope preserved: PASSED"
)


#
# -------------------------------------------------
# TEST 2
#
# start_research without scope remains supported.
# -------------------------------------------------
#

print()
print("TEST 2 - NO SCOPE")
print("-----------------")


command = ControlCommand(
    operation="start_research",
    topic=topic,
    scope=None,
)


validated = validator.validate(
    command=command,
    context=context,
)


assert (
    validated.topic
    == topic
)

assert (
    validated.scope
    is None
)


print(
    "Optional scope compatibility: PASSED"
)


#
# -------------------------------------------------
# TEST 3
#
# Blank initial scope is equivalent to no scope.
# -------------------------------------------------
#

print()
print("TEST 3 - BLANK INITIAL SCOPE")
print("----------------------------")


command = ControlCommand(
    operation="start_research",
    topic=topic,
    scope="   ",
)


validated = validator.validate(
    command=command,
    context=context,
)


assert (
    validated.scope
    is None
)


print(
    "Blank initial scope normalization: PASSED"
)


#
# -------------------------------------------------
# TEST 4
#
# Topic normalization.
# -------------------------------------------------
#

print()
print("TEST 4 - TOPIC NORMALIZATION")
print("----------------------------")


command = ControlCommand(
    operation="start_research",
    topic=f"  {topic}  ",
    scope=scope,
)


validated = validator.validate(
    command=command,
    context=context,
)


assert (
    validated.topic
    == topic
)

assert (
    validated.scope
    == scope
)


print(
    "Topic normalization: PASSED"
)


#
# -------------------------------------------------
# TEST 5
#
# modify_scope retains its stricter semantics.
# -------------------------------------------------
#

print()
print("TEST 5 - MODIFY SCOPE REMAINS STRICT")
print("------------------------------------")


active_context = ControlContext(
    session_id="test-session",
    topic=topic,
    scope=scope,
    status="researching",
)


try:

    validator.validate(
        command=ControlCommand(
            operation="modify_scope",
            scope="   ",
        ),
        context=active_context,
    )

except ValueError:

    print(
        "Blank replacement scope rejected: PASSED"
    )

else:

    raise AssertionError(
        "modify_scope accepted a blank "
        "replacement scope."
    )


print()
print("===========================")
print("PASS")
print("===========================")

print(
    "ControlCommandValidator correctly "
    "distinguishes initial research scope "
    "from replacement research scope."
)