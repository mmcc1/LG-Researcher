from abc import ABC, abstractmethod

from domain.web import RetrievedDocument


class DocumentRetriever(ABC):

    @abstractmethod
    def retrieve(
        self,
        url: str,
    ) -> RetrievedDocument:
        pass