from dataclasses import dataclass

from langchain_core.language_models.chat_models import (
    BaseChatModel,
)


@dataclass(frozen=True)
class AgentModels:

    planner: BaseChatModel

    researcher: BaseChatModel

    summariser: BaseChatModel

    reviewer: BaseChatModel

    reporter: BaseChatModel

    controller: BaseChatModel