
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

import requests

from domain.search import SearchResult
from search.base import SearchProvider


class LangSearchSearchProvider(SearchProvider):

    API_URL = "https://api.langsearch.com/v1/web-search"

    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 30.0,
        max_attempts: int = 3,
        retry_delay_seconds: float = 2.0,
    ):

        if not api_key or not api_key.strip():

            raise ValueError(
                "LangSearch API key is required."
            )

        if timeout_seconds <= 0:

            raise ValueError(
                "LangSearch timeout must be positive."
            )

        if max_attempts < 1:

            raise ValueError(
                "LangSearch max_attempts must be at least 1."
            )

        if retry_delay_seconds < 0:

            raise ValueError(
                "LangSearch retry delay cannot be negative."
            )

        self.api_key = api_key.strip()
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds

    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchResult]:

        if not query or not query.strip():

            return []

        if max_results < 1:

            raise ValueError(
                "max_results must be greater than zero."
            )

        if max_results > 50:

            raise ValueError(
                "LangSearch supports at most 50 results."
            )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "query": query,
            "freshness": "noLimit",
            "summary": False,
            "count": max_results,
        }

        last_exception = None

        for attempt in range(
            1,
            self.max_attempts + 1,
        ):

            try:

                response = requests.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )

                if response.status_code in {
                    408,
                    429,
                    500,
                    502,
                    503,
                    504,
                }:

                    response.raise_for_status()

                if response.status_code >= 400:

                    response.raise_for_status()

                response_data = response.json()

                return self._parse_results(
                    response_data=response_data,
                    query=query,
                    max_results=max_results,
                )

            except (
                requests.Timeout,
                requests.ConnectionError,
            ) as ex:

                last_exception = ex

            except requests.HTTPError as ex:

                last_exception = ex

                status_code = (
                    ex.response.status_code
                    if ex.response is not None
                    else None
                )

                if status_code not in {
                    408,
                    429,
                    500,
                    502,
                    503,
                    504,
                }:

                    raise RuntimeError(
                        "LangSearch rejected the request "
                        f"with HTTP status {status_code}."
                    ) from ex

            except (
                ValueError,
                TypeError,
                KeyError,
            ) as ex:

                raise RuntimeError(
                    "LangSearch returned an invalid response."
                ) from ex

            if attempt < self.max_attempts:

                time.sleep(
                    self.retry_delay_seconds
                    * attempt
                )

        print(
            "LangSearch failed after "
            f"{self.max_attempts} attempts "
            f"for query: {query}"
        )

        print(
            f"Reason: {last_exception}"
        )

        return []

    def _parse_results(
        self,
        response_data: dict,
        query: str,
        max_results: int,
    ) -> list[SearchResult]:

        if not isinstance(response_data, dict):

            raise ValueError(
                "LangSearch response must be an object."
            )

        data = response_data.get(
            "data"
        )

        if not isinstance(data, dict):

            raise ValueError(
                "LangSearch response is missing data."
            )

        web_pages = data.get(
            "webPages"
        )

        if web_pages is None:

            return []

        if not isinstance(web_pages, dict):

            raise ValueError(
                "LangSearch webPages must be an object."
            )

        raw_results = web_pages.get(
            "value",
            [],
        )

        if not isinstance(raw_results, list):

            raise ValueError(
                "LangSearch result value must be a list."
            )

        results = []

        for item in raw_results:

            if len(results) >= max_results:

                break

            if not isinstance(item, dict):

                continue

            url = item.get(
                "url",
                "",
            )

            if not isinstance(url, str):

                continue

            url = url.strip()

            if not url:

                continue

            title = item.get(
                "name",
                "",
            )

            snippet = item.get(
                "snippet",
                "",
            )

            if not isinstance(title, str):

                title = ""

            if not isinstance(snippet, str):

                snippet = ""

            result = SearchResult(
                url=url,
                title=title,
                snippet=snippet,
                rank=len(results) + 1,
                query=query,
                provider="langsearch",
            )

            results.append(result)

        return results
