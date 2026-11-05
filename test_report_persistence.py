from domain.report import (
    ResearchReport,
    ReportSection,
)

from persistence.database import (
    SessionLocal,
)

from persistence.report_repository import (
    ReportRepository,
)


SESSION_ID = (
    "063bd913-9e9a-48bd-81d7-8738153a7863"
)


def main():

    #
    # This is deliberately a persistence test,
    # not a real final research report.
    #

    report = ResearchReport(
        title=(
            "Bitcoin Persistence Test"
        ),
        executive_summary=(
            "This report exists only to test "
            "report persistence and retrieval."
        ),
        sections=[
            ReportSection(
                heading=(
                    "Origins"
                ),
                content=(
                    "Bitcoin was created under "
                    "the pseudonym Satoshi Nakamoto."
                ),
                reviewed_claim_ids=[
                    6,
                    10,
                ],
            ),
            ReportSection(
                heading=(
                    "Technical Foundation"
                ),
                content=(
                    "Bitcoin uses blockchain, "
                    "cryptographic mechanisms, "
                    "and Proof-of-Work."
                ),
                reviewed_claim_ids=[
                    1,
                    2,
                    3,
                    4,
                    5,
                ],
            ),
        ],
        conclusions=(
            "Persistence and provenance can be "
            "tested without invoking the Report "
            "Agent."
        ),
        limitations=[
            (
                "This is test data and is not the "
                "final research report."
            ),
        ],
    )

    #
    # Save.
    #

    with SessionLocal() as db:

        repository = (
            ReportRepository(db)
        )

        if repository.exists_for_session(
            SESSION_ID
        ):

            raise RuntimeError(
                "A report already exists for "
                "this session. Do not overwrite it."
            )

        entity = repository.save(
            session_id=SESSION_ID,
            report=report,
        )

        print(
            "Report persisted."
        )

        print(
            f"Report ID: {entity.id}"
        )

    #
    # Use a completely new SQLAlchemy session
    # for the read test.
    #
    # This demonstrates that we're reconstructing
    # persisted state rather than seeing objects
    # still present in the original unit of work.
    #

    with SessionLocal() as db:

        repository = (
            ReportRepository(db)
        )

        persisted = (
            repository.get_for_session(
                SESSION_ID
            )
        )

    if persisted is None:

        raise RuntimeError(
            "Persisted report could not be read."
        )

    print()
    print(
        "Report read from database."
    )

    print(
        f"Report ID: {persisted.id}"
    )

    print(
        f"Session ID: "
        f"{persisted.research_session_id}"
    )

    print(
        f"Title: {persisted.title}"
    )

    print()

    for section in (
        persisted.sections
    ):

        print(
            f"Section {section.ordinal}: "
            f"{section.heading}"
        )

        print(
            "Reviewed claim IDs: "
            + ", ".join(
                str(claim_id)
                for claim_id
                in section.reviewed_claim_ids
            )
        )

    print()

    print("Limitations:")

    for limitation in (
        persisted.limitations
    ):

        print(
            f"- {limitation}"
        )


if __name__ == "__main__":

    main()