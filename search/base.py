from abc import ABC, abstractmethod

from domain.search import SearchResult


class SearchProvider(ABC):

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> list[SearchResult]:
        pass