from nodes.check_existing_search import (
    CheckExistingSearchNode,
)
from persistence.database import SessionLocal


node = CheckExistingSearchNode(
    session_factory=SessionLocal,
)


def test_question(
    session_id: str,
    question_id: int,
    description: str,
):

    print()
    print("=" * 60)
    print(description)
    print("=" * 60)

    state = {
        "session_id": session_id,
        "current_question_id": question_id,
    }

    result = node(state)

    print()
    print(
        "search_required:",
        result["search_required"],
    )

    print(
        "current_search_attempt_id:",
        result[
            "current_search_attempt_id"
        ],
    )

    return result


#
# TEST 1
#
# Question 90 already has search results from
# before SearchAttempt existed.
#
# It must NOT search again.
#

legacy_result = test_question(
    session_id=(
        "8b89d73a-c2b5-4b15-a6c5-bb71e43064b5"
    ),
    question_id=90,
    description=(
        "TEST 1 - Existing legacy search"
    ),
)

assert (
    legacy_result["search_required"]
    is False
)

assert (
    legacy_result[
        "current_search_attempt_id"
    ]
    is None
)


#
# TEST 2
#
# Question 94 has no search results.
#
# The first call should create an initial
# SearchAttempt and require a search.
#

first_result = test_question(
    session_id=(
        "076c529a-365a-43ec-81ff-bb3780d195b1"
    ),
    question_id=94,
    description=(
        "TEST 2 - New search attempt"
    ),
)

assert (
    first_result["search_required"]
    is True
)

attempt_id = first_result[
    "current_search_attempt_id"
]

assert attempt_id is not None


#
# TEST 3
#
# Simulate recovery.
#
# Call the node again without completing the
# attempt. It must reuse the SAME running
# SearchAttempt rather than create another one.
#

second_result = test_question(
    session_id=(
        "076c529a-365a-43ec-81ff-bb3780d195b1"
    ),
    question_id=94,
    description=(
        "TEST 3 - Recover running attempt"
    ),
)

assert (
    second_result["search_required"]
    is True
)

assert (
    second_result[
        "current_search_attempt_id"
    ]
    == attempt_id
)


print()
print("=" * 60)
print("PASS")
print("=" * 60)
print(
    "Legacy searches are reused and running "
    "SearchAttempts survive recovery."
)