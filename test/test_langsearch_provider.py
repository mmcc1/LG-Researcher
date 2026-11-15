
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

from unittest.mock import MagicMock, patch

import requests

from config import SearchSettings

from search.duckduckgo import DuckDuckGoSearchProvider
from search.langsearch import LangSearchSearchProvider
from search.search_provider_factory import SearchProviderFactory


def create_test_settings(
    provider: str,
    api_key: str | None = None,
) -> SearchSettings:

    return SearchSettings(
        provider=provider,
        langsearch_api_key=api_key,
        langsearch_timeout_seconds=30.0,
        langsearch_max_attempts=3,
        langsearch_retry_delay_seconds=0.0,
    )


def test_factory():

    duckduckgo_settings = create_test_settings(
        provider="duckduckgo",
    )

    duckduckgo_provider = SearchProviderFactory.create(
        settings=duckduckgo_settings,
    )

    assert isinstance(
        duckduckgo_provider,
        DuckDuckGoSearchProvider,
    )

    langsearch_settings = create_test_settings(
        provider="langsearch",
        api_key="test-api-key",
    )

    langsearch_provider = SearchProviderFactory.create(
        settings=langsearch_settings,
    )

    assert isinstance(
        langsearch_provider,
        LangSearchSearchProvider,
    )

    print(
        "Search provider factory: PASSED"
    )


def test_successful_search():

    response = MagicMock()

    response.status_code = 200

    response.json.return_value = {
        "data": {
            "webPages": {
                "value": [
                    {
                        "url": "https://example.com/first",
                        "name": "First result",
                        "snippet": "First snippet",
                    },
                    {
                        "url": "https://example.com/second",
                        "name": "Second result",
                        "snippet": "Second snippet",
                    },
                ]
            }
        }
    }

    provider = LangSearchSearchProvider(
        api_key="test-api-key",
        retry_delay_seconds=0.0,
    )

    with patch(
        "search.langsearch.requests.post",
        return_value=response,
    ) as post:

        results = provider.search(
            query="quantum computing bitcoin",
            max_results=2,
        )

    assert len(results) == 2

    assert results[0].url == "https://example.com/first"
    assert results[0].title == "First result"
    assert results[0].snippet == "First snippet"
    assert results[0].rank == 1
    assert results[0].query == "quantum computing bitcoin"
    assert results[0].provider == "langsearch"

    assert results[1].rank == 2

    post.assert_called_once()

    request_arguments = post.call_args.kwargs

    assert request_arguments["json"]["count"] == 2

    assert (
        request_arguments["headers"]["Authorization"]
        == "Bearer test-api-key"
    )

    print(
        "LangSearch response mapping: PASSED"
    )


def test_retry():

    response = MagicMock()

    response.status_code = 200

    response.json.return_value = {
        "data": {
            "webPages": {
                "value": []
            }
        }
    }

    provider = LangSearchSearchProvider(
        api_key="test-api-key",
        max_attempts=3,
        retry_delay_seconds=0.0,
    )

    with patch(
        "search.langsearch.requests.post",
        side_effect=[
            requests.Timeout("Simulated timeout"),
            response,
        ],
    ) as post:

        results = provider.search(
            query="retry test",
        )

    assert results == []
    assert post.call_count == 2

    print(
        "LangSearch transient failure retry: PASSED"
    )


def test_invalid_response():

    response = MagicMock()

    response.status_code = 200

    response.json.return_value = {
        "unexpected": "response"
    }

    provider = LangSearchSearchProvider(
        api_key="test-api-key",
        retry_delay_seconds=0.0,
    )

    with patch(
        "search.langsearch.requests.post",
        return_value=response,
    ):

        try:

            provider.search(
                query="invalid response test",
            )

        except RuntimeError as ex:

            assert (
                "invalid response"
                in str(ex)
            )

        else:

            raise AssertionError(
                "Invalid response was not rejected."
            )

    print(
        "LangSearch invalid response handling: PASSED"
    )


def test_missing_api_key():

    try:

        create_test_settings(
            provider="langsearch",
            api_key=None,
        )

    except ValueError:

        pass

    else:

        raise AssertionError(
            "Missing LangSearch API key was accepted."
        )

    print(
        "LangSearch API key validation: PASSED"
    )


def main():

    print()
    print(
        "LANGSEARCH PROVIDER TEST"
    )

    test_factory()
    test_successful_search()
    test_retry()
    test_invalid_response()
    test_missing_api_key()

    print()
    print(
        "LangSearch provider tests: PASSED"
    )


if __name__ == "__main__":

    main()
