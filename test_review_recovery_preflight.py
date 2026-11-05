from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.review_repository import (
    ReviewRepository,
)

from persistence.report_repository import (
    ReportRepository,
)


SESSION_ID = (
    "fae69e3e-58d2-4c6a-8ac1-85cf6994db06"
)

QUESTION_ID = 100


print()
print(
    "REVIEW RECOVERY PREFLIGHT TEST"
)
print(
    "=============================="
)


with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    review_repository = (
        ReviewRepository(db)
    )

    report_repository = (
        ReportRepository(db)
    )

    research_session = (
        session_repository.get(
            SESSION_ID
        )
    )

    if research_session is None:
        raise ValueError(
            "Research session not found."
        )

    questions = (
        session_repository.get_questions(
            SESSION_ID
        )
    )

    question = (
        session_repository.get_question(
            QUESTION_ID
        )
    )

    if question is None:
        raise ValueError(
            "Research question not found."
        )

    review_exists = (
        review_repository.exists_for_question(
            QUESTION_ID
        )
    )

    report_exists = (
        report_repository.exists_for_session(
            SESSION_ID
        )
    )


print()
print(
    f"Session status: "
    f"{research_session.status}"
)

print()
print("QUESTIONS")
print("---------")

for item in questions:

    with SessionLocal() as db:

        review_repository = (
            ReviewRepository(db)
        )

        item_review_exists = (
            review_repository
            .exists_for_question(
                item.id
            )
        )

    print(
        f"Question {item.id}: "
        f"{item.status}, "
        f"review exists = "
        f"{item_review_exists}"
    )


print()
print("FAILED QUESTION")
print("---------------")

print(
    f"Question ID: "
    f"{question.id}"
)

print(
    f"Question status: "
    f"{question.status}"
)

print(
    f"Review exists: "
    f"{review_exists}"
)

print()
print(
    f"Report exists: "
    f"{report_exists}"
)


#
# The failed Q100 review must not have been
# persisted.
#

assert (
    review_exists
    is False
)

assert (
    report_exists
    is False
)


print()
print(
    "=============================="
)
print("PASS")
print(
    "=============================="
)

print(
    "Failed review left no invalid "
    "durable review or report."
)