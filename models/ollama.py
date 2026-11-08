from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama

from models.base import ChatModelProvider


class OllamaChatModelProvider(ChatModelProvider):

    def __init__(
        self,
        model_name: str,
        base_url: str = "http://localhost:11434",
        temperature: float = 0.2,
        timeout_seconds: float = 900.0,
    ):
        self.model_name = model_name
        self.base_url = base_url
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds

    def create(self) -> BaseChatModel:
        return ChatOllama(
            model=self.model_name,
            base_url=self.base_url,
            temperature=self.temperature,
            client_kwargs={
            "timeout": self.timeout_seconds,
        },
        )