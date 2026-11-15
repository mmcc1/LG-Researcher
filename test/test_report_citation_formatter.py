
#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

from persistence.database import (
    SessionLocal,
)

from persistence.report_repository import (
    ReportRepository,
)

from processing.report_citation_resolver import (
    ReportCitationResolver,
)

from processing.report_citation_registry import (
    ReportCitationRegistry,
)

from processing.report_text_formatter import (
    ReportTextFormatter,
)


def main():

    session_id = input(
        "Research session ID: "
    ).strip()

    if not session_id:

        raise ValueError(
            "A research session ID is required."
        )

    with SessionLocal() as db:

        report_repository = (
            ReportRepository(db)
        )

        report = report_repository.get_for_session(
            session_id
        )

        if report is None:

            raise ValueError(
                "No persisted report exists "
                "for this session."
            )

        reviewed_claim_ids = []

        for section in report.sections:

            reviewed_claim_ids.extend(
                section.reviewed_claim_ids
            )

        resolver = ReportCitationResolver(
            db
        )

        provenance = resolver.resolve(
            session_id=session_id,
            reviewed_claim_ids=reviewed_claim_ids,
        )

    registry_builder = ReportCitationRegistry()

    registry = registry_builder.build(
        report=report,
        provenance=provenance,
    )

    formatter = ReportTextFormatter()

    report_text = formatter.format(
        report=report,
        citation_registry=registry,
    )

    assert "BIBLIOGRAPHY" in report_text

    assert "Reviewed claim IDs:" not in report_text

    assert "Sources cited:" in report_text

    for entry in registry.bibliography:

        reference = (
            f"[{entry.number}] {entry.title}"
        )

        assert reference in report_text

        assert entry.url in report_text

    print()
    print(
        "REPORT CITATION FORMATTER"
    )

    print()
    print(
        f"Report: {report.title}"
    )

    print(
        f"Sections: {len(report.sections)}"
    )

    print(
        "Bibliography entries: "
        f"{len(registry.bibliography)}"
    )

    print(
        "Formatted report length: "
        f"{len(report_text):,} characters"
    )

    print()
    print(
        "Bibliography generation: PASSED"
    )

    print(
        "Internal claim footer removal: PASSED"
    )

    print(
        "Citation references: PASSED"
    )

    print()
    print(
        "REPORT PREVIEW"
    )

    print()
    print(
        report_text
    )


if __name__ == "__main__":

    main()
