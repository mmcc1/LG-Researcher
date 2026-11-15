
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

from config import SearchSettings

from search.base import SearchProvider
from search.duckduckgo import DuckDuckGoSearchProvider
from search.langsearch import LangSearchSearchProvider


class SearchProviderFactory:

    @staticmethod
    def create(
        settings: SearchSettings,
    ) -> SearchProvider:

        provider = settings.provider.strip().lower()

        if provider == "duckduckgo":

            return DuckDuckGoSearchProvider()

        if provider == "langsearch":

            return LangSearchSearchProvider(
                api_key=settings.langsearch_api_key,
                timeout_seconds=settings.langsearch_timeout_seconds,
                max_attempts=settings.langsearch_max_attempts,
                retry_delay_seconds=settings.langsearch_retry_delay_seconds,
            )

        raise ValueError(
            f"Unsupported search provider: {provider}"
        )
