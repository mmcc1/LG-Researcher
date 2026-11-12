
from langchain_core.messages import (
    HumanMessage,
)

from config import (
    settings,
)

from models.factory import (
    ChatModelFactory,
)


model_settings = settings.planner_model

print(
    f"Provider: {model_settings.provider}"
)

print(
    f"Model: {model_settings.model_name}"
)

model = ChatModelFactory.create(
    model_settings
)

response = model.invoke(
    [
        HumanMessage(
            content=(
                "Reply with exactly: "
                "OpenAI connection successful."
            )
        )
    ]
)

print()
print(response.content)
