from langchain_core.language_models.chat_models import BaseChatModel

from config import ModelSettings
from models.ollama import OllamaChatModelProvider


class ChatModelFactory:

    @staticmethod
    def create(
        settings: ModelSettings,
    ) -> BaseChatModel:

        provider = settings.provider.lower()

        if provider == "ollama":

            model_provider = OllamaChatModelProvider(
                model_name=settings.model_name,
                base_url=settings.base_url,
                temperature=settings.temperature,
            )

            return model_provider.create()

        raise ValueError(
            f"Unsupported model provider: "
            f"{settings.provider}"
        )