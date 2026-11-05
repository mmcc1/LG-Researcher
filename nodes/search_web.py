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