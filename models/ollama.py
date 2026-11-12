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