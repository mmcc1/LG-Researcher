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

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):

    query: str = Field(
        description="The web search query to execute."
    )

    rationale: str = Field(
        description=(
            "Why this search query is useful for answering "
            "the research question."
        )
    )


class SearchPlan(BaseModel):

    queries: list[SearchQuery] = Field(
        description=(
            "A small set of focused web searches that should "
            "be performed to investigate the research question."
        )
    )


class SearchResult(BaseModel):

    url: str

    title: str

    snippet: str

    rank: int

    query: str

    provider: str