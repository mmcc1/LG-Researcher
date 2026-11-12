from domain.search import SearchResult

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

TEST_URL = (
    "https://example.com/"
    "rollback-test"
)


print()
print(
    "SEARCH TRANSACTION ROLLBACK TEST"
)
print(
    "================================"
)


#
# Create a new attempt specifically for this test.
#

with SessionLocal() as db:

    repository = (
        SearchAttemptRepository(db)
    )

    attempt = repository.create(
        session_id=SESSION_ID,
        question_id=QUESTION_ID,
        purpose="deeper_research",
        instructions=(
            "Synthetic attempt used only "
            "for rollback testing."
        ),
    )

    attempt_id = attempt.id

    repository.mark_running(
        attempt_id
    )

    print()
    print(
        f"Created running attempt "
        f"{attempt_id}."
    )


#
# Synthetic search result.
#

results = [
    SearchResult(
        query=(
            "transaction rollback test"
        ),
        provider="rollback-test",
        rank=1,
        url=TEST_URL,
        title=(
            "Rollback Test Result"
        ),
        snippet=(
            "This result must not survive "
            "the transaction rollback."
        ),
    )
]


#
# Begin the same transaction pattern used by
# SaveSearchResultsNode, but deliberately fail
# before the attempt can be completed.
#

try:

    with SessionLocal() as db:

        search_repository = (
            SearchRepository(db)
        )

        attempt_repository = (
            SearchAttemptRepository(db)
        )

        try:

            search_repository.add_results(
                session_id=SESSION_ID,
                question_id=QUESTION_ID,
                results=results,
            )

            print(
                "Search result added to "
                "uncommitted transaction."
            )

            #
            # Simulate a process/application failure
            # before attempt completion and commit.
            #

            raise RuntimeError(
                "Simulated failure."
            )

            #
            # This code must never execute.
            #

            attempt_repository.set_completed(
                attempt_id
            )

            db.commit()

        except Exception:

            print(
                "Failure detected. "
                "Rolling back transaction."
            )

            db.rollback()

            raise

except RuntimeError as exc:

    assert (
        str(exc)
        == "Simulated failure."
    )

    print(
        "Simulated failure handled."
    )


#
# Open a completely new database session.
#
# This proves we're looking at durable database
# state rather than objects remaining in the
# rolled-back SQLAlchemy session.
#

with SessionLocal() as db:

    search_repository = (
        SearchRepository(db)
    )

    attempt_repository = (
        SearchAttemptRepository(db)
    )

    attempt = attempt_repository.get(
        attempt_id
    )

    assert attempt is not None

    #
    # The attempt was committed as running before
    # the failed transaction began, so it should
    # still be running.
    #

    assert (
        attempt.status
        == "running"
    )

    assert (
        attempt.completed_at
        is None
    )

    print()
    print(
        "Attempt remains running."
    )

    #
    # The synthetic search result was part of the
    # rolled-back transaction, so it must not exist.
    #

    persisted_results = (
        search_repository
        .get_results_for_question(
            QUESTION_ID
        )
    )

    matching_results = [
        item
        for item in persisted_results
        if item.url == TEST_URL
    ]

    assert (
        len(matching_results)
        == 0
    )

    print(
        "Uncommitted search result "
        "was rolled back."
    )


print()
print(
    "================================"
)
print(
    "PASS"
)
print(
    "================================"
)
print(
    "Failed search persistence left "
    "no partial durable state."
)