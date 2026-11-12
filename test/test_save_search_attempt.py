from domain.search import SearchResult

from nodes.save_search_results import (
    SaveSearchResultsNode,
)

from persistence.database import (
    SessionLocal,
)

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)

from persistence.search_repository import (
    SearchRepository,
)


SESSION_ID = (
    "076c529a-365a-43ec-81ff-bb3780d195b1"
)

QUESTION_ID = 94

ATTEMPT_ID = 2


print()
print(
    "ATOMIC SEARCH PERSISTENCE TEST"
)
print(
    "=============================="
)


#
# Confirm our test attempt is still running.
#

with SessionLocal() as db:

    attempt_repository = (
        SearchAttemptRepository(db)
    )

    attempt = attempt_repository.get(
        ATTEMPT_ID
    )

    assert attempt is not None

    assert (
        attempt.status
        == "running"
    )

    print()
    print(
        f"Attempt {ATTEMPT_ID} "
        "is running."
    )


#
# Construct one fake search result.
#
# No network request is made.
#

results = [
    SearchResult(
        query=(
            "SHA-256 practical "
            "collision attack"
        ),
        provider="test",
        rank=1,
        url=(
            "https://example.com/"
            "test-search-attempt"
        ),
        title=(
            "Test Search Result"
        ),
        snippet=(
            "Synthetic result used only "
            "to test transactional "
            "persistence."
        ),
    )
]


state = {
    "session_id": SESSION_ID,
    "current_question_id": QUESTION_ID,
    "current_search_attempt_id":
        ATTEMPT_ID,
    "search_results": results,
}


node = SaveSearchResultsNode(
    session_factory=SessionLocal,
)


result = node(
    state
)


assert (
    result[
        "current_search_attempt_id"
    ]
    is None
)


#
# Verify BOTH sides became durable.
#

with SessionLocal() as db:

    attempt_repository = (
        SearchAttemptRepository(db)
    )

    search_repository = (
        SearchRepository(db)
    )

    attempt = attempt_repository.get(
        ATTEMPT_ID
    )

    assert attempt is not None

    assert (
        attempt.status
        == "completed"
    )

    assert (
        attempt.completed_at
        is not None
    )

    search_results = (
        search_repository
        .get_results_for_question(
            QUESTION_ID
        )
    )

    matching_results = [
        item
        for item in search_results
        if item.provider == "test"
        and item.url
        == (
            "https://example.com/"
            "test-search-attempt"
        )
    ]

    assert len(
        matching_results
    ) == 1

    print()
    print(
        "Search result persisted."
    )

    print(
        "Search attempt completed."
    )


print()
print(
    "=============================="
)
print(
    "PASS"
)
print(
    "=============================="
)
print(
    "Search results and attempt "
    "completion were persisted "
    "together."
)