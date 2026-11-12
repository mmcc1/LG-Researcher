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
