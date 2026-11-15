
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
            ReportRepository(
                db
            )
        )

        report = (
            report_repository.get_for_session(
                session_id
            )
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

        print()
        print(
            "REPORT CITATION RESOLUTION"
        )

        print()
        print(
            f"Report: {report.title}"
        )

        print(
            "Reviewed claims: "
            f"{len(provenance.claims)}"
        )

        for claim in provenance.claims:

            print()
            print(
                "Reviewed claim: "
                f"{claim.reviewed_claim_id}"
            )

            print(
                "Supporting sources:"
            )

            for source in (
                claim.supporting_sources
            ):

                print(
                    f"  Source {source.source_id}: "
                    f"{source.title}"
                )

                print(
                    f"    {source.final_url}"
                )

            print(
                "Contradicting sources:"
            )

            if not claim.contradicting_sources:

                print(
                    "  None"
                )

            for source in (
                claim.contradicting_sources
            ):

                print(
                    f"  Source {source.source_id}: "
                    f"{source.title}"
                )

                print(
                    f"    {source.final_url}"
                )

        print()
        print(
            "Citation resolution: PASSED"
        )


if __name__ == "__main__":

    main()
