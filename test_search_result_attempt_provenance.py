from domain.search import (
    SearchResult,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)

from persistence.search_repository import (
    SearchRepository,
)


print()
print(
    "SEARCH RESULT ATTEMPT "
    "PROVENANCE TEST"
)
print(
    "=============================="
)


#
# Create isolated session/question.
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        session_repository.create(
            topic=(
                "Search attempt provenance test"
            )
        )
    )

    session_id = research_session.id

    question = (
        session_repository.add_question(
            session_id=session_id,
            question=(
                "Synthetic provenance question?"
            ),
        )
    )

    question_id = question.id


#
# Create and start an isolated attempt.
#

with SessionLocal() as db:

    attempt_repository = (
        SearchAttemptRepository(db)
    )

    attempt = attempt_repository.create(
        session_id=session_id,
        question_id=question_id,
        purpose="initial",
    )

    attempt_id = attempt.id

    attempt_repository.mark_running(
        attempt_id
    )


print(
    f"Session ID: {session_id}"
)

print(
    f"Question ID: {question_id}"
)

print(
    f"Attempt ID: {attempt_id}"
)


#
# Persist synthetic search result with explicit
# attempt provenance.
#

result = SearchResult(
    query=(
        "synthetic provenance query"
    ),
    # rationale=(
    #     "Synthetic query used only "
    #     "for persistence testing."
    # ),
    provider="provenance-test",
    rank=1,
    url=(
        "https://example.com/"
        "search-attempt-provenance"
    ),
    title=(
        "Search Attempt Provenance Test"
    ),
    snippet=(
        "Synthetic search result."
    ),
)


with SessionLocal() as db:

    repository = (
        SearchRepository(db)
    )

    repository.save_results(
        session_id=session_id,
        question_id=question_id,
        results=[
            result
        ],
        attempt_id=attempt_id,
    )


#
# Reload using the attempt itself.
#

with SessionLocal() as db:

    repository = (
        SearchRepository(db)
    )

    results = (
        repository.get_results_for_attempt(
            attempt_id
        )
    )

    assert len(results) == 1

    persisted = results[0]

    assert (
        persisted.research_session_id
        == session_id
    )

    assert (
        persisted.research_question_id
        == question_id
    )

    assert (
        persisted.search_attempt_id
        == attempt_id
    )

    assert (
        persisted.provider
        == "provenance-test"
    )


print()
print(
    "Persisted result:"
)

print(
    f"  Result ID:  {persisted.id}"
)

print(
    f"  Session:    "
    f"{persisted.research_session_id}"
)

print(
    f"  Question:   "
    f"{persisted.research_question_id}"
)

print(
    f"  Attempt:    "
    f"{persisted.search_attempt_id}"
)

print(
    f"  Provider:   "
    f"{persisted.provider}"
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
    "WebSearchResult retains its "
    "SearchAttempt provenance."
)