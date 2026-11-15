
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

from config import settings

from domain.search import (
    SearchPlan,
    SearchQuery,
    SearchResult,
)

from nodes.search_web import SearchWebNode

from search.langsearch import (
    LangSearchSearchProvider,
)

from search.search_provider_factory import (
    SearchProviderFactory,
)


def main():

    print()
    print("LANGSEARCH SEARCH NODE INTEGRATION TEST")
    print("======================================")
    print()

    assert settings.search.provider == "langsearch", (
        "Set SEARCH_PROVIDER=langsearch in .env "
        "before running this test."
    )

    search_provider = SearchProviderFactory.create(
        settings=settings.search,
    )

    assert isinstance(
        search_provider,
        LangSearchSearchProvider,
    )

    print(
        "LangSearch provider selected: PASSED"
    )

    search_plan = SearchPlan(
        queries=[
            SearchQuery(
                query=(
                    "Bitcoin quantum computing "
                    "ECDSA Shor algorithm"
                ),
                rationale=(
                    "Identify technical explanations "
                    "of the quantum threat to Bitcoin."
                ),
            ),
            SearchQuery(
                query=(
                    "Bitcoin post quantum cryptography "
                    "signature migration"
                ),
                rationale=(
                    "Identify proposed approaches "
                    "to quantum-resistant signatures."
                ),
            ),
        ]
    )

    results_per_query = 3

    search_node = SearchWebNode(
        search_provider=search_provider,
        results_per_query=results_per_query,
    )

    state = {
        "search_plan": search_plan,
    }

    print()
    print(
        f"Search queries: {len(search_plan.queries)}"
    )
    print(
        f"Maximum results per query: {results_per_query}"
    )
    print()

    output = search_node(
        state
    )

    assert isinstance(
        output,
        dict,
    )

    assert "search_results" in output

    print()
    print(
        "Search node output structure: PASSED"
    )

    results = output[
        "search_results"
    ]

    assert isinstance(
        results,
        list,
    )

    assert results, (
        "SearchWebNode returned no results."
    )

    assert len(results) <= (
        len(search_plan.queries)
        * results_per_query
    )

    expected_queries = {
        search_query.query
        for search_query in search_plan.queries
    }

    for result in results:

        assert isinstance(
            result,
            SearchResult,
        )

        assert result.provider == "langsearch"

        assert result.query in expected_queries

        assert isinstance(
            result.rank,
            int,
        )

        assert result.rank >= 1

        assert isinstance(
            result.url,
            str,
        )

        assert result.url.strip()

        assert isinstance(
            result.title,
            str,
        )

        assert isinstance(
            result.snippet,
            str,
        )

    print(
        "Search result model validation: PASSED"
    )

    print(
        "Search provider identification: PASSED"
    )

    print(
        "Search query correlation: PASSED"
    )

    print()
    print(
        f"Total search results: {len(results)}"
    )

    for search_query in search_plan.queries:

        query_results = [
            result
            for result in results
            if result.query == search_query.query
        ]

        print()
        print(
            f"Query: {search_query.query}"
        )

        print(
            f"Results: {len(query_results)}"
        )

        for result in query_results:

            print()
            print(
                f"  Rank: {result.rank}"
            )
            print(
                f"  Title: {result.title}"
            )
            print(
                f"  URL: {result.url}"
            )
            print(
                f"  Provider: {result.provider}"
            )

    print()
    print(
        "LangSearch SearchWebNode integration: PASSED"
    )


if __name__ == "__main__":

    main()
