
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

import tempfile

from pathlib import Path
from uuid import UUID

from application.report_file_writer import (
    ReportFileWriter,
)

from persistence.database import (
    SessionLocal,
)

from persistence.report_repository import (
    ReportRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
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


def get_session_status(
    session_id: str,
) -> str:

    with SessionLocal() as db:

        repository = ResearchSessionRepository(
            db
        )

        research_session = repository.get(
            session_id
        )

        if research_session is None:

            raise ValueError(
                "Research session not found."
            )

        return research_session.status


def load_formatted_report(
    session_id: str,
) -> tuple[str, object]:

    with SessionLocal() as db:

        report_repository = ReportRepository(
            db
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

    citation_registry = registry_builder.build(
        report=report,
        provenance=provenance,
    )

    formatter = ReportTextFormatter()

    report_text = formatter.format(
        report=report,
        citation_registry=citation_registry,
    )

    return (
        report_text,
        citation_registry,
    )


def main():

    session_id = input(
        "Research session ID: "
    ).strip()

    session_id = str(
        UUID(session_id)
    )

    status_before = get_session_status(
        session_id
    )

    report_text, citation_registry = (
        load_formatted_report(
            session_id
        )
    )

    with tempfile.TemporaryDirectory(
        prefix="lgresearcher-export-"
    ) as temporary_directory:

        output_directory = Path(
            temporary_directory
        )

        writer = ReportFileWriter(
            output_directory=output_directory
        )

        output_path = writer.write(
            session_id=session_id,
            report_text=report_text,
        )

        expected_path = (
            output_directory
            / f"{session_id}.txt"
        )

        assert output_path == expected_path, (
            "Unexpected report output path."
        )

        assert output_path.is_file(), (
            "Report output file was not created."
        )

        exported_text = output_path.read_text(
            encoding="utf-8"
        )

        assert exported_text == report_text, (
            "Exported report differs "
            "from formatted report."
        )

        assert "BIBLIOGRAPHY" in exported_text, (
            "Exported report has no bibliography."
        )

        assert "Reviewed claim IDs:" not in exported_text, (
            "Internal reviewed claim footer "
            "appears in exported report."
        )

        for entry in citation_registry.bibliography:

            reference = (
                f"[{entry.number}] {entry.title}"
            )

            assert reference in exported_text, (
                "Missing bibliography entry: "
                f"{entry.number}"
            )

            assert entry.url in exported_text, (
                "Missing bibliography URL: "
                f"{entry.number}"
            )

        temporary_files = list(
            output_directory.glob(
                "*.tmp"
            )
        )

        hidden_temporary_files = list(
            output_directory.glob(
                ".*.tmp"
            )
        )

        assert not temporary_files, (
            "Temporary export files remain."
        )

        assert not hidden_temporary_files, (
            "Hidden temporary export files remain."
        )

        second_output_path = writer.write(
            session_id=session_id,
            report_text=report_text,
        )

        assert second_output_path == output_path, (
            "Repeated export changed "
            "the destination path."
        )

        second_exported_text = (
            second_output_path.read_text(
                encoding="utf-8"
            )
        )

        assert second_exported_text == report_text, (
            "Repeated export produced "
            "different content."
        )

        print()
        print(
            "REPORT FILE EXPORT"
        )

        print()
        print(
            f"Session ID: {session_id}"
        )

        print(
            f"Output path: {output_path}"
        )

        print(
            "Exported characters: "
            f"{len(exported_text):,}"
        )

        print(
            "Bibliography entries: "
            f"{len(citation_registry.bibliography)}"
        )

        print()
        print(
            "File creation: PASSED"
        )

        print(
            "Content verification: PASSED"
        )

        print(
            "Bibliography verification: PASSED"
        )

        print(
            "Temporary file cleanup: PASSED"
        )

        print(
            "Repeated export: PASSED"
        )

    assert not output_directory.exists(), (
        "Temporary export directory "
        "was not removed."
    )

    status_after = get_session_status(
        session_id
    )

    assert status_after == status_before, (
        "Research session status changed "
        "during the export test."
    )

    print(
        "Temporary directory cleanup: PASSED"
    )

    print(
        "Session status unchanged: PASSED"
    )

    print()
    print(
        "Report file export: PASSED"
    )


if __name__ == "__main__":

    main()
