
#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete

from config import settings

from domain.search import (
    SearchPlan,
    SearchQuery,
    SearchResult,
)

from nodes.search_web import SearchWebNode
from nodes.save_search_results import SaveSearchResultsNode

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseFenceRejected,
)

from persistence.search_repository import SearchRepository

from persistence.models import (
    ResearchSession,
    ResearchQuestion,
    SearchAttempt,
    WebSearchResult,
)

from search.langsearch import LangSearchSearchProvider

from search.search_provider_factory import (
    SearchProviderFactory,
)


def create_test_records(
    session_id: str,
) -> tuple[int, int]:

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    with SessionLocal() as db:

        research_session = ResearchSession(
            id=session_id,
            topic="LangSearch persistence integration test",
            scope="Disposable integration test records.",
            status="researching",
            pause_requested=False,
            execution_lease_version=0,
            created_at=now,
            updated_at=now,
        )

        db.add(
            research_session
        )

        db.flush()

        research_question = ResearchQuestion(
            research_session_id=session_id,
            category="Technical research",
            question=(
                "How could quantum computing "
                "affect Bitcoin signatures?"
            ),
            rationale=(
                "Verify LangSearch result persistence."
            ),
            status="researching",
            created_at=now,
            updated_at=now,
        )

        db.add(
            research_question
        )

        db.flush()

        question_id = research_question.id

        search_attempt = SearchAttempt(
            research_session_id=session_id,
            research_question_id=question_id,
            purpose="initial",
            status="running",
            instructions=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )

        db.add(
            search_attempt
        )

        db.flush()

        attempt_id = search_attempt.id

        db.commit()

    return question_id, attempt_id


def delete_test_records(
    session_id: str,
) -> None:

    with SessionLocal() as db:

        try:

            db.execute(
                delete(WebSearchResult).where(
                    WebSearchResult.research_session_id
                    == session_id
                )
            )

            db.execute(
                delete(SearchAttempt).where(
                    SearchAttempt.research_session_id
                    == session_id
                )
            )

            db.execute(
                delete(ResearchQuestion).where(
                    ResearchQuestion.research_session_id
                    == session_id
                )
            )

            db.execute(
                delete(ResearchSession).where(
                    ResearchSession.id
                    == session_id
                )
            )

            db.commit()

        except Exception:

            db.rollback()

            raise


def get_persisted_results(
    attempt_id: int,
) -> list[SearchResult]:

    with SessionLocal() as db:

        repository = SearchRepository(
            db
        )

        entities = repository.get_results_for_attempt(
            attempt_id=attempt_id,
        )

        results = []

        for entity in entities:

            results.append(
                SearchResult(
                    url=entity.url,
                    title=entity.title,
                    snippet=entity.snippet,
                    rank=entity.rank,
                    query=entity.query,
                    provider=entity.provider,
                )
            )

        return results


def verify_attempt_completed(
    attempt_id: int,
) -> None:

    with SessionLocal() as db:

        attempt = db.get(
            SearchAttempt,
            attempt_id,
        )

        assert attempt is not None

        assert attempt.status == "completed"

        assert attempt.completed_at is not None



def verify_results(
    expected_results: list[SearchResult],
    actual_results: list[SearchResult],
) -> None:

    assert len(actual_results) == len(
        expected_results
    ), (
        "Result count mismatch: "
        f"expected={len(expected_results)}, "
        f"actual={len(actual_results)}"
    )

    fields = (
        "url",
        "title",
        "snippet",
        "rank",
        "query",
        "provider",
    )

    for index, (expected, actual) in enumerate(
        zip(
            expected_results,
            actual_results,
        ),
        start=1,
    ):

        for field in fields:

            expected_value = getattr(
                expected,
                field,
            )

            actual_value = getattr(
                actual,
                field,
            )

            if expected_value != actual_value:

                print()
                print(
                    f"Result {index}, field '{field}' differs."
                )

                print(
                    f"Expected length: "
                    f"{len(str(expected_value))}"
                )

                print(
                    f"Actual length: "
                    f"{len(str(actual_value))}"
                )

                print(
                    f"Expected: {expected_value!r}"
                )

                print(
                    f"Actual: {actual_value!r}"
                )

                raise AssertionError(
                    "Persisted result differs "
                    "from original LangSearch result."
                )

        assert actual.provider == "langsearch"



def main():

    print()
    print("LANGSEARCH SQL PERSISTENCE INTEGRATION TEST")
    print("==========================================")
    print()

    if settings.search.provider != "langsearch":

        raise RuntimeError(
            "Set SEARCH_PROVIDER=langsearch "
            "before running this test."
        )

    provider = SearchProviderFactory.create(
        settings=settings.search,
    )

    assert isinstance(
        provider,
        LangSearchSearchProvider,
    )

    print(
        "LangSearch provider selected: PASSED"
    )

    session_id = str(
        uuid4()
    )

    question_id = None
    attempt_id = None
    lease = None

    try:

        question_id, attempt_id = create_test_records(
            session_id=session_id,
        )

        print(
            "Disposable SQL records created: PASSED"
        )

        with SessionLocal() as db:

            lease = ExecutionLeaseRepository(
                db
            ).acquire(
                session_id=session_id,
                duration_seconds=300,
            )

        print(
            "Execution lease acquired: PASSED"
        )

        search_plan = SearchPlan(
            queries=[
                SearchQuery(
                    query=(
                        "Bitcoin quantum computing "
                        "ECDSA Shor algorithm"
                    ),
                    rationale=(
                        "Find technical explanations "
                        "of quantum risks to Bitcoin."
                    ),
                ),
            ]
        )

        search_node = SearchWebNode(
            search_provider=provider,
            results_per_query=3,
        )

        search_state = {
            "search_plan": search_plan,
        }

        search_output = search_node(
            search_state
        )

        results = search_output[
            "search_results"
        ]

        assert results

        assert all(
            result.provider == "langsearch"
            for result in results
        )

        print(
            "Live LangSearch results obtained: PASSED"
        )

        save_node = SaveSearchResultsNode(
            session_factory=SessionLocal,
        )

        persistence_state = {
            "session_id": session_id,
            "current_question_id": question_id,
            "current_search_attempt_id": attempt_id,
            "search_results": results,
        }

        config = {
            "configurable": {
                "execution_lease": lease,
            }
        }

        save_output = save_node(
            persistence_state,
            config,
        )

        assert save_output == {}

        print(
            "Search results saved through production node: PASSED"
        )

        persisted_results = get_persisted_results(
            attempt_id=attempt_id,
        )

        verify_results(
            expected_results=results,
            actual_results=persisted_results,
        )

        print(
            "Persisted result values: PASSED"
        )

        verify_attempt_completed(
            attempt_id=attempt_id,
        )

        print(
            "Search attempt completed: PASSED"
        )

        save_node(
            persistence_state,
            config,
        )

        repeated_results = get_persisted_results(
            attempt_id=attempt_id,
        )

        verify_results(
            expected_results=results,
            actual_results=repeated_results,
        )

        print(
            "Idempotent repeated save: PASSED"
        )

        different_result = results[0].model_copy(
            update={
                "title": "Modified test result",
            }
        )

        different_state = {
            **persistence_state,
            "search_results": [
                different_result,
                *results[1:],
            ],
        }

        try:

            save_node(
                different_state,
                config,
            )

        except ValueError as ex:

            assert (
                "different persisted results"
                in str(ex)
            )

        else:

            raise AssertionError(
                "A completed search attempt accepted "
                "different results."
            )

        print(
            "Conflicting repeated save rejected: PASSED"
        )

        missing_lease_config = {
            "configurable": {}
        }

        try:

            save_node(
                persistence_state,
                missing_lease_config,
            )

        except RuntimeError as ex:

            assert (
                "Execution lease is missing"
                in str(ex)
            )

        else:

            raise AssertionError(
                "Save succeeded without an execution lease."
            )

        print(
            "Missing execution lease rejected: PASSED"
        )

        with SessionLocal() as db:

            released = ExecutionLeaseRepository(
                db
            ).release(
                lease
            )

        assert released

        print(
            "Execution lease released: PASSED"
        )

        try:

            save_node(
                persistence_state,
                config,
            )

        except ExecutionLeaseFenceRejected:

            pass

        else:

            raise AssertionError(
                "Save succeeded using a released lease."
            )

        print(
            "Released execution lease rejected: PASSED"
        )

        print()
        print(
            "LangSearch SQL persistence integration: PASSED"
        )

    finally:

        if lease is not None:

            with SessionLocal() as db:

                ExecutionLeaseRepository(
                    db
                ).release(
                    lease
                )

        if question_id is not None:

            delete_test_records(
                session_id=session_id,
            )

            print(
                "Disposable SQL records cleaned up: PASSED"
            )


if __name__ == "__main__":

    main()
