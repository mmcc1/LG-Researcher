from agents.control_agent import (
    ControlAgent,
)

from domain.control import (
    ControlContext,
)

from models.factory import (
    ChatModelFactory,
)

from config import (
    create_model_settings,
)


#
# -------------------------------------------------
# Configuration
# -------------------------------------------------
#
# This test uses the real configured controller
# model.
#
# Environment variables, when present:
#
# CONTROLLER_PROVIDER
# CONTROLLER_MODEL
# CONTROLLER_BASE_URL
# CONTROLLER_TEMPERATURE
#
# Otherwise the normal defaults are used.
# -------------------------------------------------
#


settings = (
    create_model_settings(
        "CONTROLLER"
    )
)


model = (
    ChatModelFactory.create(
        settings
    )
)


agent = (
    ControlAgent(
        model=model
    )
)


#
# -------------------------------------------------
# Contexts
# -------------------------------------------------
#


running_context = (
    ControlContext(
        session_id="test-session",
        topic=(
            "The potential effect of quantum "
            "computing on Bitcoin"
        ),
        scope=None,
        status="researching",
        pause_requested=False,
    )
)


paused_context = (
    ControlContext(
        session_id="test-session",
        topic=(
            "The potential effect of quantum "
            "computing on Bitcoin"
        ),
        scope=None,
        status="planned",
        pause_requested=True,
    )
)


#
# -------------------------------------------------
# Test helper
# -------------------------------------------------
#


def test_intent(
    user_message: str,
    expected_operation: str,
    context: ControlContext,
):

    print()
    print(
        f"USER: {user_message}"
    )

    command = (
        agent.interpret(
            user_message=user_message,
            context=context,
        )
    )

    print(
        "OPERATION: "
        f"{command.operation}"
    )

    print(
        "EXPECTED:  "
        f"{expected_operation}"
    )

    assert (
        command.operation
        == expected_operation
    ), (
        "Unexpected operation for "
        f"{user_message!r}: "
        f"expected "
        f"{expected_operation!r}, "
        f"received "
        f"{command.operation!r}"
    )

    print("RESULT: PASSED")


#
# -------------------------------------------------
# Tests
# -------------------------------------------------
#


print()
print(
    "CONTROL AGENT CONVERSATIONAL "
    "INTENT TEST"
)

print(
    "===================================="
)


#
# -------------------------------------------------
# TEST 1 - STATUS
# -------------------------------------------------
#


print()
print(
    "TEST 1 - STATUS INTENT"
)

print(
    "----------------------"
)


status_messages = [
    "what's happening?",
    "where are we?",
    "how far have we got?",
    "what stage are we at?",
    "is it finished?",
]


for message in status_messages:

    test_intent(
        user_message=message,
        expected_operation="status",
        context=running_context,
    )


#
# -------------------------------------------------
# TEST 2 - RESUME
# -------------------------------------------------
#
# Use an explicitly paused context here so the
# natural-language continuation request is
# unambiguous.
# -------------------------------------------------
#


print()
print(
    "TEST 2 - RESUME INTENT"
)

print(
    "----------------------"
)


resume_messages = [
    "continue",
    "carry on",
    "keep going",
    "continue the research",
    "resume the research",
]


for message in resume_messages:

    test_intent(
        user_message=message,
        expected_operation="resume",
        context=paused_context,
    )


#
# -------------------------------------------------
# TEST 3 - PAUSE
# -------------------------------------------------
#


print()
print(
    "TEST 3 - PAUSE INTENT"
)

print(
    "---------------------"
)


pause_messages = [
    "pause",
    "stop",
    "hold it there",
    "stop the research",
    "pause the research",
]


for message in pause_messages:

    test_intent(
        user_message=message,
        expected_operation="pause",
        context=running_context,
    )


#
# -------------------------------------------------
# TEST 4 - CONDITIONAL PAUSE
# -------------------------------------------------
#
# These requests cannot currently be represented
# faithfully by ControlCommand.
#
# The agent must not silently discard the requested
# future-boundary condition and reduce them to an
# unconditional pause.
# -------------------------------------------------
#


print()
print(
    "TEST 4 - UNSUPPORTED CONDITIONAL PAUSE"
)

print(
    "--------------------------------------"
)


conditional_pause_messages = [
    "stop after this question",
    "pause after the current question",
]


for message in conditional_pause_messages:

    test_intent(
        user_message=message,
        expected_operation="help",
        context=running_context,
    )


#
# -------------------------------------------------
# TEST 5 - STATUS VS RESUME
# -------------------------------------------------
#
# Both are tested against a paused context.
#
# Asking about the state is status.
# Asking to change the state is resume.
# -------------------------------------------------
#


print()
print(
    "TEST 5 - STATUS VS RESUME"
)

print(
    "-------------------------"
)


test_intent(
    user_message=(
        "are we paused?"
    ),
    expected_operation="status",
    context=paused_context,
)


test_intent(
    user_message=(
        "continue from where we stopped"
    ),
    expected_operation="resume",
    context=paused_context,
)


#
# -------------------------------------------------
# TEST 6 - STATUS VS PAUSE
# -------------------------------------------------
#


print()
print(
    "TEST 6 - STATUS VS PAUSE"
)

print(
    "------------------------"
)


test_intent(
    user_message=(
        "is the research stopped?"
    ),
    expected_operation="status",
    context=running_context,
)


test_intent(
    user_message=(
        "stop the research"
    ),
    expected_operation="pause",
    context=running_context,
)


#
# -------------------------------------------------
# Complete
# -------------------------------------------------
#


print()
print(
    "===================================="
)

print(
    "PASS"
)

print(
    "===================================="
)

print(
    "The Control Agent correctly maps "
    "conversational requests onto the "
    "existing deterministic control "
    "operations without inventing "
    "unsupported pause semantics."
)