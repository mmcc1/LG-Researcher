from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


print()
print(
    "COUNTER-EVIDENCE CANDIDATE SEARCH"
)
print(
    "================================="
)


with SessionLocal() as db:

    #
    # We deliberately query through the ORM here
    # because ResearchSessionRepository does not
    # currently expose a list-all method.
    #

    from persistence.models import (
        ResearchSession,
    )

    sessions = (
        db.query(
            ResearchSession
        )
        .filter(
            ResearchSession.status.in_(
                [
                    "researching",
                    "researched",
                ]
            )
        )
        .order_by(
            ResearchSession.created_at.desc()
        )
        .all()
    )

    if not sessions:

        print()
        print(
            "No researching/researched "
            "sessions found."
        )

    for research_session in sessions:

        repository = (
            ResearchSessionRepository(db)
        )

        questions = (
            repository.get_questions(
                research_session.id
            )
        )

        researched_questions = [
            question
            for question in questions
            if question.status == "researched"
        ]

        if not researched_questions:
            continue

        print()
        print(
            "SESSION"
        )
        print(
            "-------"
        )

        print(
            f"ID: "
            f"{research_session.id}"
        )

        print(
            f"Topic: "
            f"{research_session.topic}"
        )

        print(
            f"Status: "
            f"{research_session.status}"
        )

        print()
        print(
            "RESEARCHED QUESTIONS"
        )
        print(
            "--------------------"
        )

        for question in researched_questions:

            print()
            print(
                f"Question ID: "
                f"{question.id}"
            )

            print(
                f"Question: "
                f"{question.question}"
            )


print()
print(
    "================================="
)
print(
    "Candidate search complete."
)