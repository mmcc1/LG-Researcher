from graph.research_graph import (
    route_after_research_completion,
)


print()
print(
    "RESEARCH EXECUTION TARGET TEST"
)
print(
    "=============================="
)


#
# Only execution_target matters to this router.
# It does not inspect the rest of ResearchState.
#

research_state = {
    "execution_target": "research",
}

complete_state = {
    "execution_target": "complete",
}


print()
print(
    "Testing research-only target..."
)

result = (
    route_after_research_completion(
        research_state
    )
)

print(
    f"Route: {result}"
)

assert result == "stop"


print()
print(
    "Testing complete target..."
)

result = (
    route_after_research_completion(
        complete_state
    )
)

print(
    f"Route: {result}"
)

assert result == "review"


print()
print(
    "Testing default behaviour..."
)

result = (
    route_after_research_completion(
        {}
    )
)

print(
    f"Route: {result}"
)

assert result == "review"


print()
print(
    "Testing invalid target..."
)

try:

    route_after_research_completion(
        {
            "execution_target": (
                "invalid"
            )
        }
    )

except ValueError as ex:

    print(
        f"Expected error: {ex}"
    )

else:

    raise AssertionError(
        "Invalid execution target "
        "was not rejected."
    )


print()
print(
    "=============================="
)
print("PASS")
print(
    "=============================="
)