from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
)


class ResearchWorkflowResult(BaseModel):

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    session_id: str
    topic: str
    graph_result: dict[str, Any]