
from langchain_core.language_models.chat_models import (
    BaseChatModel,
)

from langchain_openai import (
    ChatOpenAI,
)


class OpenAIChatModelProvider:

    def __init__(
        self,
        model_name: str,
        api_key: str,
        temperature: float,
        timeout_seconds: float,
        base_url: str | None = None,
    ):

        self.model_name = model_name
        self.api_key = api_key
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self.base_url = base_url

    def create(
        self,
    ) -> BaseChatModel:

        if not self.api_key.strip():

            raise ValueError(
                "OPENAI_API_KEY must be configured "
                "when using the OpenAI provider."
            )

        model_arguments = {
            "model": self.model_name,
            "api_key": self.api_key,
            "timeout": self.timeout_seconds,
        }

        if self.base_url is not None:

            model_arguments["base_url"] = (
                self.base_url
            )

        if self.temperature is not None:

            model_arguments["temperature"] = (
                self.temperature
            )

        return ChatOpenAI(
            **model_arguments
        )
