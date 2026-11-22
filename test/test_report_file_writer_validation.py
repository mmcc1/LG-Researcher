from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

import pytest

from application.report_file_writer import (
    ReportFileWriter,
)


SESSION_ID = str(uuid4())


def test_output_directory_created(
    tmp_path,
):

    output_directory = (
        tmp_path / "reports" / "research"
    )

    assert not output_directory.exists()

    writer = ReportFileWriter(
        output_directory=output_directory,
    )

    output_path = writer.write(
        session_id=SESSION_ID,
        report_text="Research report.",
    )

    assert output_directory.is_dir()

    assert output_path.is_file()

    assert output_path == (
        output_directory
        / f"{SESSION_ID}.txt"
    )


def test_report_content_preserved(
    tmp_path,
):

    writer = ReportFileWriter(
        output_directory=tmp_path,
    )

    report_text = (
        "Research report\n"
        "Executive summary\n"
        "Research findings\n"
        "Conclusions\n"
    )

    output_path = writer.write(
        session_id=SESSION_ID,
        report_text=report_text,
    )

    assert output_path.read_text(
        encoding="utf-8"
    ) == report_text

    assert output_path.read_bytes() == (
        report_text.encode("utf-8")
    )


def test_unicode_report_preserved(
    tmp_path,
):

    writer = ReportFileWriter(
        output_directory=tmp_path,
    )

    report_text = (
        "International research — Étude scientifique\n"
        "神経科学 — Neuroscience\n"
        "研究、ข้อมูล、café、α + β.\n"
        "Données limitées — 数据有限\n"
    )

    output_path = writer.write(
        session_id=SESSION_ID,
        report_text=report_text,
    )

    assert output_path.read_bytes() == (
        report_text.encode("utf-8")
    )

    assert output_path.read_text(
        encoding="utf-8"
    ) == report_text


def test_existing_report_replaced(
    tmp_path,
):

    writer = ReportFileWriter(
        output_directory=tmp_path,
    )

    first_text = (
        "Original research report."
    )

    second_text = (
        "Replacement research report."
    )

    first_path = writer.write(
        session_id=SESSION_ID,
        report_text=first_text,
    )

    second_path = writer.write(
        session_id=SESSION_ID,
        report_text=second_text,
    )

    assert first_path == second_path

    assert second_path.read_text(
        encoding="utf-8"
    ) == second_text

    assert list(
        tmp_path.iterdir()
    ) == [
        second_path
    ]


def test_repeated_publication_is_idempotent(
    tmp_path,
):

    writer = ReportFileWriter(
        output_directory=tmp_path,
    )

    report_text = (
        "Repeatable research report.\n"
        "BIBLIOGRAPHY\n"
    )

    first_path = writer.write(
        session_id=SESSION_ID,
        report_text=report_text,
    )

    first_content = (
        first_path.read_bytes()
    )

    for _ in range(3):

        repeated_path = writer.write(
            session_id=SESSION_ID,
            report_text=report_text,
        )

        assert repeated_path == first_path

        assert (
            repeated_path.read_bytes()
            == first_content
        )

    assert list(
        tmp_path.iterdir()
    ) == [
        first_path
    ]


def test_session_id_canonicalized(
    tmp_path,
):

    writer = ReportFileWriter(
        output_directory=tmp_path,
    )

    output_path = writer.write(
        session_id=SESSION_ID.upper(),
        report_text="Research report.",
    )

    assert output_path.name == (
        f"{SESSION_ID}.txt"
    )


@pytest.mark.parametrize(
    "session_id",
    [
        "",
        "invalid-session-id",
        "../report",
        "../../report",
        r"..\..\report",
        "/report.txt",
    ],
)
def test_invalid_session_id_rejected(
    tmp_path,
    session_id,
):

    output_directory = (
        tmp_path / "reports"
    )

    writer = ReportFileWriter(
        output_directory=output_directory,
    )

    with pytest.raises(
        ValueError,
    ):

        writer.write(
            session_id=session_id,
            report_text="Invalid report.",
        )

    assert not output_directory.exists()

    assert not list(
        tmp_path.iterdir()
    )


def test_string_output_directory_accepted(
    tmp_path,
):

    writer = ReportFileWriter(
        output_directory=str(tmp_path),
    )

    output_path = writer.write(
        session_id=SESSION_ID,
        report_text="Research report.",
    )

    assert isinstance(
        output_path,
        Path,
    )

    assert output_path.is_file()


def test_empty_report_written(
    tmp_path,
):

    writer = ReportFileWriter(
        output_directory=tmp_path,
    )

    output_path = writer.write(
        session_id=SESSION_ID,
        report_text="",
    )

    assert output_path.is_file()

    assert output_path.read_bytes() == b""


def test_synchronization_precedes_replacement(
    tmp_path,
):

    writer = ReportFileWriter(
        output_directory=tmp_path,
    )

    report_text = (
        "Complete synchronized report."
    )

    events = []

    import os

    original_fsync = os.fsync

    original_replace = os.replace

    def tracked_fsync(
        file_descriptor,
    ):

        events.append(
            "fsync"
        )

        return original_fsync(
            file_descriptor
        )

    def tracked_replace(
        source,
        destination,
    ):

        events.append(
            "replace"
        )

        source_path = Path(
            source
        )

        destination_path = Path(
            destination
        )

        assert (
            source_path.parent
            == destination_path.parent
        )

        assert source_path.suffix == ".tmp"

        assert (
            source_path.read_bytes()
            == report_text.encode("utf-8")
        )

        assert not destination_path.exists()

        return original_replace(
            source,
            destination,
        )

    with patch(
        "application.report_file_writer.os.fsync",
        side_effect=tracked_fsync,
    ):

        with patch(
            "application.report_file_writer.os.replace",
            side_effect=tracked_replace,
        ):

            output_path = writer.write(
                session_id=SESSION_ID,
                report_text=report_text,
            )

    assert events == [
        "fsync",
        "replace",
    ]

    assert output_path.is_file()

    assert list(
        tmp_path.iterdir()
    ) == [
        output_path
    ]


@pytest.mark.parametrize(
    "existing_report",
    [
        False,
        True,
    ],
)
@pytest.mark.parametrize(
    "failed_operation",
    [
        "fsync",
        "replace",
    ],
)
def test_publication_failure_preserves_files(
    tmp_path,
    existing_report,
    failed_operation,
):

    writer = ReportFileWriter(
        output_directory=tmp_path,
    )

    output_path = (
        tmp_path
        / f"{SESSION_ID}.txt"
    )

    original_text = (
        "Original valid research report."
    )

    if existing_report:

        writer.write(
            session_id=SESSION_ID,
            report_text=original_text,
        )

    patch_target = (
        "application.report_file_writer.os."
        f"{failed_operation}"
    )

    with patch(
        patch_target,
        side_effect=OSError(
            "Simulated publication failure."
        ),
    ):

        with pytest.raises(
            OSError,
            match="Simulated publication failure.",
        ):

            writer.write(
                session_id=SESSION_ID,
                report_text="Replacement report.",
            )

    assert not list(
        tmp_path.glob("*.tmp")
    )

    if existing_report:

        assert output_path.is_file()

        assert output_path.read_text(
            encoding="utf-8"
        ) == original_text

        assert list(
            tmp_path.iterdir()
        ) == [
            output_path
        ]

    else:

        assert not output_path.exists()

        assert not list(
            tmp_path.iterdir()
        )


def test_recovery_after_failed_replacement(
    tmp_path,
):

    writer = ReportFileWriter(
        output_directory=tmp_path,
    )

    original_path = writer.write(
        session_id=SESSION_ID,
        report_text="Original report.",
    )

    replacement_text = (
        "Successfully recovered report."
    )

    with patch(
        "application.report_file_writer.os.replace",
        side_effect=OSError(
            "Simulated replacement failure."
        ),
    ):

        with pytest.raises(
            OSError,
            match="Simulated replacement failure.",
        ):

            writer.write(
                session_id=SESSION_ID,
                report_text=replacement_text,
            )

    assert original_path.read_text(
        encoding="utf-8"
    ) == "Original report."

    recovered_path = writer.write(
        session_id=SESSION_ID,
        report_text=replacement_text,
    )

    assert recovered_path == original_path

    assert recovered_path.read_text(
        encoding="utf-8"
    ) == replacement_text

    assert list(
        tmp_path.iterdir()
    ) == [
        recovered_path
    ]


def test_encoding_failure_preserves_existing_report(
    tmp_path,
):

    writer = ReportFileWriter(
        output_directory=tmp_path,
    )

    original_text = (
        "Original research report."
    )

    output_path = writer.write(
        session_id=SESSION_ID,
        report_text=original_text,
    )

    invalid_text = (
        "Invalid Unicode surrogate: \ud800"
    )

    with pytest.raises(
        UnicodeEncodeError,
    ):

        writer.write(
            session_id=SESSION_ID,
            report_text=invalid_text,
        )

    assert output_path.read_text(
        encoding="utf-8"
    ) == original_text

    assert list(
        tmp_path.iterdir()
    ) == [
        output_path
    ]