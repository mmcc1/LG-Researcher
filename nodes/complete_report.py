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

from sqlalchemy.orm import (
    sessionmaker,
)

from langchain_core.runnables import (
    RunnableConfig,
)

from application.report_file_writer import (
    ReportFileWriter,
)

from config import (
    settings,
)

from graph.state import (
    ResearchState,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
)

from persistence.report_repository import (
    ReportRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from processing.report_text_formatter import (
    ReportTextFormatter,
)


class CompleteReportNode:

    def __init__(
        self,
        session_factory: sessionmaker,
    ):

        self.session_factory = (
            session_factory
        )

        self.report_formatter = (
            ReportTextFormatter()
        )

        self.report_file_writer = (
            ReportFileWriter(
                output_directory=(
                    settings.report_output_directory
                ),
            )
        )

    def __call__(
        self,
        state: ResearchState,
        config: RunnableConfig,
    ) -> dict:

        session_id = state["session_id"]

        configurable = config.get(
            "configurable",
            {},
        )

        lease = configurable.get(
            "execution_lease"
        )

        if not isinstance(
            lease,
            ExecutionLease,
        ):

            raise RuntimeError(
                "Execution lease is missing "
                "from graph configuration."
            )

        if lease.session_id != session_id:

            raise ValueError(
                "Execution lease does not match "
                "the research session."
            )

        execution_guard = configurable.get(
            "execution_guard"
        )

        if (
            execution_guard is not None
            and not callable(execution_guard)
        ):

            raise TypeError(
                "Execution guard must be callable."
            )

        if execution_guard is not None:

            execution_guard()

        #
        # Load the validated, persisted report.
        #

        with self.session_factory() as db:

            report_repository = (
                ReportRepository(db)
            )

            report = (
                report_repository.get_for_session(
                    session_id
                )
            )

        if report is None:

            raise RuntimeError(
                "Cannot complete research session "
                "because no persisted report exists."
            )

        #
        # Format the persisted report.
        #

        report_text = (
            self.report_formatter.format(
                report
            )
        )

        if execution_guard is not None:

            execution_guard()

        #
        # Write the report to the configured
        # output directory.
        #

        report_path = (
            self.report_file_writer.write(
                session_id=session_id,
                report_text=report_text,
            )
        )

        print()
        print(
            "Final research report saved:"
        )

        print(
            report_path
        )

        if execution_guard is not None:

            execution_guard()

        #
        # The repository validates the lease,
        # verifies durable report existence,
        # and completes the session atomically.
        #
        # The file export must succeed before
        # this completion transition.
        #

        with self.session_factory() as db:

            session_repository = (
                ResearchSessionRepository(db)
            )

            session_repository.complete_report_fenced(
                session_id=session_id,
                lease=lease,
            )

        print()
        print(
            "Research session completed."
        )

        return {}
