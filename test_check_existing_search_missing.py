from persistence.database import (
    SessionLocal,
)

from persistence.models import (
    ResearchQuestion,
    WebSearchResult,
)

from nodes.check_existing_search import (
    CheckExistingSearchNode,
)


#
# Find a research question that has no
# persisted search results.
#

with SessionLocal() as db:

    question = (
        db.query(ResearchQuestion)
        .outerjoin(
            WebSearchResult,
            WebSearchResult.research_question_id
            == ResearchQuestion.id,
        )
        .filter(
            WebSearchResult.id.is_(None)
        )
        .order_by(
            ResearchQuestion.id.desc()
        )
        .first()
    )


if question is None:

    print(
        "No research question without "
        "search results was found."
    )

    print(
        "Nothing to test."
    )

    raise SystemExit(0)


print()
print(
    "QUESTION WITHOUT SEARCH RESULTS"
)
print(
    "==============================="
)

print(
    f"Question ID: {question.id}"
)

print(
    f"Question: {question.question}"
)


#
# Test CheckExistingSearchNode.
#

node = CheckExistingSearchNode(
    session_factory=SessionLocal,
)


state = {
    "current_question_id": question.id,
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
    f"Search required: "
    f"{result['search_required']}"
)


assert (
    result["search_required"] is True
)


print()
print(
    "PASS: missing search results "
    "correctly require a search."
)