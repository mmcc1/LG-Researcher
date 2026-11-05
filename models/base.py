from abc import ABC, abstractmethod

from langchain_core.language_models.chat_models import BaseChatModel


class ChatModelProvider(ABC):
    """
    Creates chat models for agents.

    Agents depend on this abstraction rather than knowing
    whether the underlying model is Ollama, OpenAI, Azure,
    Anthropic, etc.
    """

    @abstractmethod
    def create(self) -> BaseChatModel:
        pass