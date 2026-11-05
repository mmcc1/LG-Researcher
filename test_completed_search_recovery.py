
from typing import get_args, get_type_hints

from sqlalchemy import select

from graph.state import ResearchState

from nodes.select_question import SelectQuestionNode
from nodes.check_existing_search import CheckExistingSearchNode
from nodes.save_search_results import SaveSearchResultsNode

from persistence.database import SessionLocal
from persistence.models import SearchAttempt, WebSearchResult
from persistence.search_repository import SearchRepository

from test_search_result_fencing import (
    create_session,
    delete_session,
    expire_lease,
)

from test_review_completion_fencing import acquire_lease

from test_review_selection_fencing import (
    create_review_question,
    set_session_status,
)


SearchResult = get_args(
    get_type_hints(ResearchState)["search_results"]
)[0]


def make_results():

    return [
        SearchResult(
            url="https://example.org/research/a",
            title="Research result A",
            snippet="Evidence from source A.",
            rank=1,
            query="research recovery",
            provider="test-provider",
        ),
        SearchResult(
            url="https://example.org/research/b",
            title="Research result B",
            snippet="Evidence from source B.",
            rank=2,
            query="research recovery",
            provider="test-provider",
        ),
    ]


def make_config(lease):

    return {
        "configurable": {
            "execution_lease": lease,
        }
    }


def make_state(session_id, question_id=None, attempt_id=None, results=None):

    return {
        "session_id": session_id,
        "topic": "Completed search recovery test",
        "resume": True,
        "resume_phase": "planned",
        "execution_target": "research",
        "current_question_id": question_id,
        "current_search_attempt_id": attempt_id,
        "search_results": results if results is not None else [],
    }


def read_attempt(attempt_id):

    with SessionLocal() as db:

        attempt = db.get(
            SearchAttempt,
            attempt_id,
        )

        assert attempt is not None

        return {
            "status": attempt.status,
            "completed_at": attempt.completed_at,
        }


def read_results(attempt_id):

    with SessionLocal() as db:

        rows = db.scalars(
            select(WebSearchResult)
            .where(
                WebSearchResult.search_attempt_id
                == attempt_id
            )
            .order_by(WebSearchResult.id)
        ).all()

        return [
            (
                row.query,
                row.provider,
                row.rank,
                row.url,
                row.title,
                row.snippet,
            )
            for row in rows
        ]


def attempt_count(question_id):

    with SessionLocal() as db:

        return db.scalar(
            select(
                __import__(
                    "sqlalchemy"
                ).func.count()
            )
            .select_from(SearchAttempt)
            .where(
                SearchAttempt.research_question_id
                == question_id
            )
        )


def assert_rejected(operation, description):

    try:

        operation()

    except Exception:

        print(f"{description}: PASSED")
        return

    raise AssertionError(
        f"{description}: operation was unexpectedly accepted."
    )


def save_results(
    session_id,
    question_id,
    attempt_id,
    results,
    lease,
):

    node = SaveSearchResultsNode(
        session_factory=SessionLocal,
    )

    return node(
        make_state(
            session_id,
            question_id,
            attempt_id,
            results,
        ),
        make_config(lease),
    )


def resolve_search(
    session_id,
    question_id,
    lease,
):

    node = CheckExistingSearchNode(
        session_factory=SessionLocal,
    )

    return node(
        make_state(
            session_id,
            question_id,
        ),
        make_config(lease),
    )


def select_question(
    session_id,
    lease,
):

    node = SelectQuestionNode(
        session_factory=SessionLocal,
    )

    return node(
        make_state(session_id),
        make_config(lease),
    )


def main():

    print()
    print("COMPLETED SEARCH RECOVERY")
    print("=========================")

    session_id = create_session()

    try:

        set_session_status(
            session_id,
            "planned",
        )

        question_id = create_review_question(
            session_id,
            status="pending",
        )

        other_question_id = create_review_question(
            session_id,
            status="pending",
        )

        lease = acquire_lease(
            session_id
        )

        #
        # Select the first question and create
        # its initial search attempt.
        #

        selected = select_question(
            session_id,
            lease,
        )

        assert selected["current_question_id"] == question_id

        resolved = resolve_search(
            session_id,
            question_id,
            lease,
        )

        assert resolved["search_required"] is True

        attempt_id = resolved[
            "current_search_attempt_id"
        ]

        assert attempt_id is not None

        assert read_attempt(attempt_id)["status"] == "running"

        print("TEST 1 - Running attempt created: PASSED")

        #
        # Persist results and complete the attempt.
        #

        results = make_results()

        save_results(
            session_id,
            question_id,
            attempt_id,
            results,
            lease,
        )

        assert read_attempt(attempt_id)["status"] == "completed"

        assert len(read_results(attempt_id)) == 2

        print("TEST 2 - Results and completion persisted: PASSED")

        #
        # Repeated persistence with identical
        # results must not create duplicates.
        #

        before = read_results(
            attempt_id
        )

        save_results(
            session_id,
            question_id,
            attempt_id,
            results,
            lease,
        )

        assert read_results(attempt_id) == before

        print("TEST 3 - Identical retry is idempotent: PASSED")

        #
        # A completed attempt must reject
        # a different result set.
        #

        changed_results = make_results()

        changed_results[0] = changed_results[0].model_copy(
            update={
                "snippet": "Changed evidence.",
            }
        )

        assert_rejected(
            lambda: save_results(
                session_id,
                question_id,
                attempt_id,
                changed_results,
                lease,
            ),
            "TEST 4 - Conflicting retry rejected",
        )

        assert read_results(attempt_id) == before

        #
        # Recovery should skip the web search.
        #

        resolved = resolve_search(
            session_id,
            question_id,
            lease,
        )

        assert resolved["search_required"] is False

        assert resolved["current_search_attempt_id"] is None

        assert attempt_count(question_id) == 1

        print("TEST 5 - Completed search reused: PASSED")

        #
        # An expired worker must not persist
        # or resolve additional work.
        #

        expire_lease(
            session_id
        )

        assert_rejected(
            lambda: save_results(
                session_id,
                question_id,
                attempt_id,
                results,
                lease,
            ),
            "TEST 6 - Expired worker save rejected",
        )

        assert_rejected(
            lambda: resolve_search(
                session_id,
                question_id,
                lease,
            ),
            "TEST 7 - Expired worker recovery rejected",
        )

        #
        # Replacement worker must reuse
        # the completed attempt history.
        #

        replacement_lease = acquire_lease(
            session_id
        )

        selected = select_question(
            session_id,
            replacement_lease,
        )

        assert selected["current_question_id"] == question_id

        resolved = resolve_search(
            session_id,
            question_id,
            replacement_lease,
        )

        assert resolved["search_required"] is False

        assert resolved["current_search_attempt_id"] is None

        assert attempt_count(question_id) == 1

        assert read_results(attempt_id) == before

        print("TEST 8 - Replacement worker reused results: PASSED")

        #
        # The attempt must not be accepted
        # against a different question.
        #

        assert_rejected(
            lambda: save_results(
                session_id,
                other_question_id,
                attempt_id,
                results,
                replacement_lease,
            ),
            "TEST 9 - Cross-question ownership rejected",
        )

        #
        # Failure must leave committed
        # results and status unchanged.
        #

        assert read_attempt(attempt_id)["status"] == "completed"

        assert read_results(attempt_id) == before

        assert attempt_count(question_id) == 1

        print("TEST 10 - Rejected operation rolled back: PASSED")

        print()
        print("PASS")

    finally:

        delete_session(
            session_id
        )


if __name__ == "__main__":

    main()
