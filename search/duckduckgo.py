import time

from ddgs import DDGS
from ddgs.exceptions import (
    DDGSException,
    RatelimitException,
    TimeoutException,
)

from domain.search import SearchResult
from search.base import SearchProvider


class DuckDuckGoSearchProvider(SearchProvider):

    def __init__(
        self,
        max_attempts: int = 3,
        retry_delay_seconds: float = 2.0,
    ):
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds

    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchResult]:

        last_exception = None

        for attempt in range(
            1,
            self.max_attempts + 1,
        ):

            try:

                with DDGS() as ddgs:

                    raw_results = ddgs.text(
                        query,
                        max_results=max_results,
                    )

                results = []

                for rank, item in enumerate(
                    raw_results,
                    start=1,
                ):

                    url = item.get(
                        "href",
                        "",
                    ).strip()

                    if not url:
                        continue

                    results.append(
                        SearchResult(
                            url=url,
                            title=item.get(
                                "title",
                                "",
                            ),
                            snippet=item.get(
                                "body",
                                "",
                            ),
                            rank=rank,
                            query=query,
                            provider="ddgs",
                        )
                    )

                return results

            except (
                RatelimitException,
                TimeoutException,
                DDGSException,
            ) as ex:

                last_exception = ex

                if attempt < self.max_attempts:

                    time.sleep(
                        self.retry_delay_seconds
                        * attempt
                    )

        print(
            f"Search failed after "
            f"{self.max_attempts} attempts "
            f"for query: {query}"
        )

        print(
            f"Reason: {last_exception}"
        )

        return []