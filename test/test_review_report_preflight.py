from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.finding_repository import (
    FindingRepository,
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


print()
print(
    "REVIEW / REPORT PREFLIGHT TEST"
)
print(
    "=============================="
)


with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    finding_repository = (
        FindingRepository(db)
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
        session_repository
        .get_questions(
            SESSION_ID
        )
    )

    print()
    print(
        f"Session ID: {SESSION_ID}"
    )

    print(
        f"Session status: "
        f"{research_session.status}"
    )

    print()
    print("QUESTIONS")
    print("---------")

    total_reviews = 0

    for question in questions:

        findings = (
            finding_repository
            .get_for_question(
                question.id
            )
        )

        review_exists = (
            review_repository
            .exists_for_question(
                question.id
            )
        )

        if review_exists:
            total_reviews += 1

        print()
        print(
            f"Question {question.id}"
        )

        print(
            f"Status: "
            f"{question.status}"
        )

        print(
            f"Findings: "
            f"{len(findings)}"
        )

        print(
            f"Review exists: "
            f"{review_exists}"
        )

    report_exists = (
        report_repository
        .exists_for_session(
            SESSION_ID
        )
    )


print()
print("SUMMARY")
print("-------")

print(
    f"Questions: "
    f"{len(questions)}"
)

print(
    f"Existing reviews: "
    f"{total_reviews}"
)

print(
    f"Existing report: "
    f"{report_exists}"
)


#
# This fixture must be exactly at the
# research -> review boundary.
#

assert (
    research_session.status
    == "researched"
)

assert len(
    questions
) > 0

assert all(
    question.status == "researched"
    for question in questions
)

assert (
    total_reviews
    == 0
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
    "Session is cleanly positioned at "
    "the research -> review boundary."
)