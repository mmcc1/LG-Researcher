from persistence.database import (
    SessionLocal,
)

from persistence.report_repository import (
    ReportRepository,
)


SESSION_ID = (
    "063bd913-9e9a-48bd-81d7-8738153a7863"
)


with SessionLocal() as db:

    repository = (
        ReportRepository(db)
    )

    report = (
        repository.get_for_session(
            SESSION_ID
        )
    )


if report is None:

    print(
        "No persisted report found."
    )

    raise SystemExit(1)


print()
print(
    "PERSISTED RESEARCH REPORT"
)
print(
    "=========================="
)

print()
print(
    f"Report ID: {report.id}"
)

print(
    "Research session: "
    f"{report.research_session_id}"
)

print()

print(
    f"TITLE\n{report.title}"
)

print()

print(
    "EXECUTIVE SUMMARY"
)

print(
    report.executive_summary
)

print()

print(
    "REPORT SECTIONS"
)
print(
    "---------------"
)


for section in report.sections:

    print()

    print(
        f"{section.ordinal}. "
        f"{section.heading}"
    )

    print()

    print(
        section.content
    )

    print()

    print(
        "Reviewed claim IDs: "
        + ", ".join(
            str(claim_id)
            for claim_id
            in section.reviewed_claim_ids
        )
    )


print()
print(
    "CONCLUSIONS"
)
print(
    "-----------"
)

print(
    report.conclusions
)


print()
print(
    "LIMITATIONS"
)
print(
    "-----------"
)


if report.limitations:

    for index, limitation in enumerate(
        report.limitations,
        start=1,
    ):

        print(
            f"{index}. {limitation}"
        )

else:

    print(
        "None recorded."
    )