from persistence.database import (
    SessionLocal,
)

from nodes.check_existing_search import (
    CheckExistingSearchNode,
)


QUESTION_ID = 90


node = CheckExistingSearchNode(
    session_factory=SessionLocal,
)


state = {
    "current_question_id": QUESTION_ID,
}


result = node(state)


print()
print(
    "CHECK EXISTING SEARCH RESULT"
)
print(
    "============================"
)

print(
    f"Question ID: {QUESTION_ID}"
)

print(
    f"Search required: "
    f"{result['search_required']}"
)


assert (
    result["search_required"] is False
)


print()
print(
    "PASS: existing search results "
    "were detected."
)