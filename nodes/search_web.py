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

from graph.state import ResearchState
from search.base import SearchProvider


class SearchWebNode:

    def __init__(
        self,
        search_provider: SearchProvider,
        results_per_query: int = 5,
    ):
        self.search_provider = search_provider
        self.results_per_query = (
            results_per_query
        )

    def __call__(
            self,
            state: ResearchState,
            ) -> dict:
         
        search_plan = state["search_plan"]

        if search_plan is None:
            raise ValueError(
                "Search plan has not been created."
            )

        all_results = []

        for search_query in search_plan.queries:

            print(
                f"Searching: {search_query.query}"
                )

            results = self.search_provider.search(
                query=search_query.query,
                max_results=self.results_per_query,
            )

            if not results:

                print(
                    "No search results for: "
                    f"{search_query.query}"
                )

                continue

            all_results.extend(results)

        if not all_results:

            print(
                "No web search results were obtained "
                "for this research question."
            )

        return {
            "search_results": all_results
        }