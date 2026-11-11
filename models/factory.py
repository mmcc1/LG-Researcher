
from langchain_core.language_models.chat_models import (
    BaseChatModel,
)

from config import (
    ModelSettings,
)

from models.ollama import (
    OllamaChatModelProvider,
)

from models.openai import (
    OpenAIChatModelProvider,
)


class ChatModelFactory:

    @staticmethod
    def create(
        settings: ModelSettings,
    ) -> BaseChatModel:

        provider = (
            settings.provider.strip().lower()
        )

        if provider == "ollama":

            model_provider = (
                OllamaChatModelProvider(
                    model_name=settings.model_name,
                    base_url=settings.base_url,
                    temperature=settings.temperature,
                    timeout_seconds=(
                        settings.timeout_seconds
                    ),
                )
            )

            return model_provider.create()

        if provider == "openai":

            model_provider = (
                OpenAIChatModelProvider(
                    model_name=settings.model_name,
                    api_key=settings.api_key or "",
                    base_url=settings.base_url,
                    temperature=settings.temperature,
                    timeout_seconds=(
                        settings.timeout_seconds
                    ),
                )
            )

            return model_provider.create()

        raise ValueError(
            f"Unsupported model provider: "
            f"{settings.provider}"
        )
