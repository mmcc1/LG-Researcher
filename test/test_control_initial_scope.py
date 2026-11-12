from agents.control_agent import (
    ControlAgent,
)

from config import settings

from domain.control import (
    ControlContext,
)

from models.factory import (
    ChatModelFactory,
)

from processing.control_command_validator import (
    ControlCommandValidator,
)


print()
print("CONTROL INITIAL SCOPE TEST")
print("==========================")


model = ChatModelFactory.create(
    settings.controller_model
)

agent = ControlAgent(
    model=model
)

validator = ControlCommandValidator()


#
# -------------------------------------------------
# TEST 1
#
# Simple research topic.
# No separate scope was requested.
# -------------------------------------------------
#

print()
print("TEST 1 - UNSCOPED START")
print("-----------------------")


empty_context = ControlContext(
    session_id=None,
    topic=None,
    scope=None,
    status=None,
)


request = (
    "Research the effect of Bitcoin mining "
    "on energy systems."
)


command = agent.interpret(
    user_message=request,
    context=empty_context,
)

command = validator.validate(
    command=command,
    context=empty_context,
)


print(
    f"Operation:    {command.operation}"
)

print(
    f"Topic:        {command.topic}"
)

print(
    f"Scope:        {command.scope}"
)

print(
    f"Instructions: {command.instructions}"
)


assert (
    command.operation
    == "start_research"
)

assert command.topic

assert (
    command.scope
    is None
)


print(
    "Unscoped start interpretation: PASSED"
)


#
# -------------------------------------------------
# TEST 2
#
# New research with an explicitly separate,
# persistent focus.
# -------------------------------------------------
#

print()
print("TEST 2 - SCOPED START")
print("---------------------")


request = (
    "Research the effect of Bitcoin mining "
    "on energy systems, focusing specifically "
    "on electricity pricing, grid incentives, "
    "and renewable-energy investment."
)


command = agent.interpret(
    user_message=request,
    context=empty_context,
)

command = validator.validate(
    command=command,
    context=empty_context,
)


print(
    f"Operation:    {command.operation}"
)

print(
    f"Topic:        {command.topic}"
)

print(
    f"Scope:        {command.scope}"
)

print(
    f"Instructions: {command.instructions}"
)


assert (
    command.operation
    == "start_research"
)

assert command.topic

assert command.scope


scope_text = (
    command.scope.casefold()
)


assert (
    "electricity" in scope_text
)

assert (
    "grid" in scope_text
)

assert (
    "renewable" in scope_text
)


print(
    "Scoped start interpretation: PASSED"
)


#
# -------------------------------------------------
# TEST 3
#
# A detailed topic is not automatically split into
# a broad topic plus invented scope.
# -------------------------------------------------
#

print()
print("TEST 3 - DETAILED TOPIC")
print("-----------------------")


request = (
    "Research the economic effects of Bitcoin "
    "mining on electricity markets."
)


command = agent.interpret(
    user_message=request,
    context=empty_context,
)

command = validator.validate(
    command=command,
    context=empty_context,
)


print(
    f"Operation:    {command.operation}"
)

print(
    f"Topic:        {command.topic}"
)

print(
    f"Scope:        {command.scope}"
)


assert (
    command.operation
    == "start_research"
)

assert command.topic

assert (
    command.scope
    is None
)


print(
    "Detailed topic remains topic: PASSED"
)


#
# -------------------------------------------------
# TEST 4
#
# Existing-session modify_scope behavior must still
# produce a complete replacement scope.
# -------------------------------------------------
#

print()
print("TEST 4 - MODIFY EXISTING SCOPE")
print("------------------------------")


existing_scope = (
    "Focus specifically on electricity pricing "
    "and grid incentives."
)


active_context = ControlContext(
    session_id="test-session",
    topic=(
        "The effect of Bitcoin mining "
        "on energy systems"
    ),
    scope=existing_scope,
    status="researching",
)


request = (
    "Keep the existing scope, but also include "
    "the effects on renewable-energy investment."
)


command = agent.interpret(
    user_message=request,
    context=active_context,
)

command = validator.validate(
    command=command,
    context=active_context,
)


print(
    f"Operation: {command.operation}"
)

print(
    f"Topic:     {command.topic}"
)

print(
    f"Scope:     {command.scope}"
)


assert (
    command.operation
    == "modify_scope"
)

assert (
    command.topic
    is None
)

assert command.scope


replacement_scope = (
    command.scope.casefold()
)


assert (
    "electricity" in replacement_scope
)

assert (
    "grid" in replacement_scope
)

assert (
    "renewable" in replacement_scope
)


print(
    "Replacement scope interpretation: PASSED"
)


print()
print("==========================")
print("PASS")
print("==========================")

print(
    "ControlAgent correctly distinguishes "
    "research topic, initial scope, and "
    "replacement scope."
)