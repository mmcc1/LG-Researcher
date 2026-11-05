from pydantic import BaseModel, Field


class ResearchQuestionPlan(BaseModel):
    category: str = Field(
        description="The broad research category for this question."
    )

    question: str = Field(
        description="A specific question that should be researched."
    )

    rationale: str = Field(
        description=(
            "A short explanation of why answering this question "
            "is important to the overall research topic."
        )
    )


class ResearchPlan(BaseModel):
    topic: str = Field(
        description="The overall research topic."
    )

    questions: list[ResearchQuestionPlan] = Field(
        description=(
            "The specific questions that should be investigated "
            "to research the topic."
        )
    )