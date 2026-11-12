
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
