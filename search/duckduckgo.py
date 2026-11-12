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