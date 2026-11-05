from graph.research_graph import (
    route_pause,
)


print()
print("PAUSE GRAPH ROUTING TEST")
print("========================")


#
# -------------------------------------------------
# TEST 1
#
# No pause snapshot exists.
#
# This preserves compatibility with states created
# before cooperative pause support.
# -------------------------------------------------
#

print()
print("TEST 1 - MISSING FLAG")
print("---------------------")


state = {}


assert (
    route_pause(state)
    == "continue"
)


print(
    "Missing flag continues: PASSED"
)


#
# -------------------------------------------------
# TEST 2
#
# Explicit False continues.
# -------------------------------------------------
#

print()
print("TEST 2 - FALSE")
print("--------------")


state = {
    "pause_requested": False,
}


assert (
    route_pause(state)
    == "continue"
)


print(
    "False continues: PASSED"
)


#
# -------------------------------------------------
# TEST 3
#
# Explicit True suspends execution.
# -------------------------------------------------
#

print()
print("TEST 3 - TRUE")
print("-------------")


state = {
    "pause_requested": True,
}


assert (
    route_pause(state)
    == "pause"
)


print(
    "True pauses: PASSED"
)


print()
print("========================")
print("PASS")
print("========================")

print(
    "Pause routing correctly distinguishes "
    "continue from cooperative suspension."
)