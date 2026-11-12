from persistence.database import SessionLocal
from persistence.review_repository import (
    ReviewRepository,
)
from processing.report_context_builder import (
    ReportContextBuilder,
)


session_id = (
    "063bd913-9e9a-48bd-81d7-8738153a7863"
)

with SessionLocal() as db:

    repository = ReviewRepository(db)

    reviews = repository.get_for_session(
        session_id
    )

builder = ReportContextBuilder()

context = builder.build(
    reviews
)

print(
    f"Reviews loaded: {len(reviews)}"
)

print(
    f"Report context length: "
    f"{len(context):,} chars"
)

print()

print(context)