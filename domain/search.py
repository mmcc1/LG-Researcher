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