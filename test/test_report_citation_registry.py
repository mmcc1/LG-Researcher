
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


def main():

    session_id = input(
        "Research session ID: "
    ).strip()

    if not session_id:

        raise ValueError(
            "A research session ID is required."
        )

    with SessionLocal() as db:

        report_repository = ReportRepository(
            db
        )

        report = report_repository.get_for_session(
            session_id
        )

        if report is None:

            raise ValueError(
                "No persisted research report "
                "exists for this session."
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

    registry = ReportCitationRegistry()

    result = registry.build(
        report=report,
        provenance=provenance,
    )

    repeated_result = registry.build(
        report=report,
        provenance=provenance,
    )

    assert (
        result.model_dump()
        == repeated_result.model_dump()
    ), (
        "Citation numbering is not deterministic."
    )

    assert len(result.sections) == len(
        report.sections
    ), (
        "Citation section count does not "
        "match report section count."
    )

    numbers = [
        entry.number
        for entry in result.bibliography
    ]

    assert numbers == list(
        range(
            1,
            len(numbers) + 1,
        )
    ), (
        "Bibliography numbering is not consecutive."
    )

    urls = [
        entry.url
        for entry in result.bibliography
    ]

    assert len(urls) == len(
        set(urls)
    ), (
        "Duplicate bibliography URLs detected."
    )

    for entry in result.bibliography:

        assert entry.source_ids, (
            "Bibliography entry has no source IDs."
        )

        assert len(entry.source_ids) == len(
            set(entry.source_ids)
        ), (
            "Duplicate source IDs within "
            "bibliography entry."
        )

    valid_numbers = set(
        numbers
    )

    for section in result.sections:

        for number in (
            section.supporting_numbers
            + section.contradicting_numbers
        ):

            assert number in valid_numbers, (
                "Section references an unknown "
                "bibliography number."
            )

    print()
    print(
        "REPORT CITATION REGISTRY"
    )

    print()
    print(
        f"Report: {report.title}"
    )

    print(
        f"Reviewed claims: {len(provenance.claims)}"
    )

    print(
        "Unique bibliography entries: "
        f"{len(result.bibliography)}"
    )

    print()
    print(
        "SECTION REFERENCES"
    )

    for section in result.sections:

        print()
        print(
            f"Section {section.ordinal}"
        )

        print(
            "Supporting references: "
            + ", ".join(
                f"[{number}]"
                for number in section.supporting_numbers
            )
        )

        print(
            "Contradicting references: "
            + ", ".join(
                f"[{number}]"
                for number in section.contradicting_numbers
            )
        )

    print()
    print(
        "BIBLIOGRAPHY"
    )

    for entry in result.bibliography:

        print()
        print(
            f"[{entry.number}] {entry.title}"
        )

        print(
            entry.url
        )

        print(
            "Source IDs: "
            + ", ".join(
                str(source_id)
                for source_id in entry.source_ids
            )
        )

    print()
    print(
        "Deterministic numbering: PASSED"
    )

    print(
        "Unique source URLs: PASSED"
    )

    print(
        "Bibliography references: PASSED"
    )

    print(
        "Citation registry: PASSED"
    )


if __name__ == "__main__":

    main()
