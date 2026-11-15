
#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from application.report_file_writer import (
    ReportFileWriter,
)

from nodes.complete_report import (
    CompleteReportNode,
)

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


SESSION_ID = (
    "016e665d-ebf9-4c23-a640-80196506ecbe"
)


def make_lease(
    session_id: str,
) -> ExecutionLease:

    return ExecutionLease(
        session_id=session_id,
        owner="isolated-test-owner",
        version=1,
        expires_at=(
            datetime.now(timezone.utc)
            + timedelta(minutes=5)
        ),
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


def make_config(
    lease: ExecutionLease,
    execution_guard,
) -> dict:

    return {
        "configurable": {
            "execution_lease": lease,
            "execution_guard": execution_guard,
        }
    }


def test_successful_export(
    node: CompleteReportNode,
    lease: ExecutionLease,
    output_directory: Path,
) -> None:

    events = []

    def execution_guard():

        events.append(
            "guard"
        )

    def complete_report(
        repository,
        session_id,
        lease,
    ):

        events.append(
            "complete"
        )

        assert session_id == SESSION_ID

        assert lease.session_id == SESSION_ID

    original_write = node.report_file_writer.write

    def tracked_write(
        session_id,
        report_text,
    ):

        events.append(
            "write"
        )

        return original_write(
            session_id=session_id,
            report_text=report_text,
        )

    with patch.object(
        node.report_file_writer,
        "write",
        side_effect=tracked_write,
    ):

        with patch.object(
            ResearchSessionRepository,
            "complete_report_fenced",
            autospec=True,
            side_effect=complete_report,
        ):

            result = node(
                state={
                    "session_id": SESSION_ID,
                },
                config=make_config(
                    lease=lease,
                    execution_guard=execution_guard,
                ),
            )

    assert result == {}

    assert events == [
        "guard",
        "guard",
        "write",
        "guard",
        "complete",
    ], (
        f"Unexpected execution order: {events}"
    )

    output_path = (
        output_directory
        / f"{SESSION_ID}.txt"
    )

    assert output_path.is_file()

    report_text = output_path.read_text(
        encoding="utf-8"
    )

    assert "BIBLIOGRAPHY" in report_text

    assert "Sources cited:" in report_text

    print(
        "Successful export ordering: PASSED"
    )


def test_write_failure(
    node: CompleteReportNode,
    lease: ExecutionLease,
) -> None:

    completion_calls = []

    def complete_report(
        repository,
        session_id,
        lease,
    ):

        completion_calls.append(
            session_id
        )

    def failed_write(
        session_id,
        report_text,
    ):

        raise OSError(
            "Simulated report export failure."
        )

    with patch.object(
        node.report_file_writer,
        "write",
        side_effect=failed_write,
    ):

        with patch.object(
            ResearchSessionRepository,
            "complete_report_fenced",
            autospec=True,
            side_effect=complete_report,
        ):

            try:

                node(
                    state={
                        "session_id": SESSION_ID,
                    },
                    config=make_config(
                        lease=lease,
                        execution_guard=lambda: None,
                    ),
                )

            except OSError as error:

                assert (
                    str(error)
                    == "Simulated report export failure."
                )

            else:

                raise AssertionError(
                    "Expected report export failure."
                )

    assert not completion_calls, (
        "Session completion was attempted "
        "after export failure."
    )

    print(
        "Export failure handling: PASSED"
    )


def test_invalid_lease(
    node: CompleteReportNode,
    lease: ExecutionLease,
) -> None:

    invalid_lease = ExecutionLease(
        session_id=(
            "00000000-0000-0000-0000-000000000000"
        ),
        owner=lease.owner,
        version=lease.version,
        expires_at=lease.expires_at,
    )

    try:

        node(
            state={
                "session_id": SESSION_ID,
            },
            config=make_config(
                lease=invalid_lease,
                execution_guard=lambda: None,
            ),
        )

    except ValueError as error:

        assert (
            "Execution lease does not match"
            in str(error)
        )

    else:

        raise AssertionError(
            "Expected execution lease rejection."
        )

    print(
        "Mismatched lease rejection: PASSED"
    )


def test_guard_failure(
    node: CompleteReportNode,
    lease: ExecutionLease,
) -> None:

    completion_calls = []

    def execution_guard():

        raise RuntimeError(
            "Simulated execution guard rejection."
        )

    def complete_report(
        repository,
        session_id,
        lease,
    ):

        completion_calls.append(
            session_id
        )

    with patch.object(
        ResearchSessionRepository,
        "complete_report_fenced",
        autospec=True,
        side_effect=complete_report,
    ):

        try:

            node(
                state={
                    "session_id": SESSION_ID,
                },
                config=make_config(
                    lease=lease,
                    execution_guard=execution_guard,
                ),
            )

        except RuntimeError as error:

            assert (
                str(error)
                == "Simulated execution guard rejection."
            )

        else:

            raise AssertionError(
                "Expected execution guard rejection."
            )

    assert not completion_calls, (
        "Session completion was attempted "
        "after execution guard rejection."
    )

    print(
        "Execution guard rejection: PASSED"
    )


def main():

    status_before = get_session_status(
        SESSION_ID
    )

    lease = make_lease(
        SESSION_ID
    )

    with TemporaryDirectory(
        prefix="lgresearcher-node-test-"
    ) as temporary_directory:

        output_directory = Path(
            temporary_directory
        )

        node = CompleteReportNode(
            session_factory=SessionLocal,
        )

        node.report_file_writer = (
            ReportFileWriter(
                output_directory=output_directory,
            )
        )

        print()
        print(
            "COMPLETE REPORT NODE TEST"
        )

        print()

        test_successful_export(
            node=node,
            lease=lease,
            output_directory=output_directory,
        )

        test_write_failure(
            node=node,
            lease=lease,
        )

        test_invalid_lease(
            node=node,
            lease=lease,
        )

        test_guard_failure(
            node=node,
            lease=lease,
        )

    status_after = get_session_status(
        SESSION_ID
    )

    assert status_after == status_before, (
        "Research session status changed."
    )

    print(
        "Database status unchanged: PASSED"
    )

    print()
    print(
        "Complete report node: PASSED"
    )


if __name__ == "__main__":

    main()
