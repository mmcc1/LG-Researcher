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

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from domain.control import (
    ControlContext,
    ReportResult,
)

from persistence.report_repository import (
    ReportRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


class GenerateReportCommandHandler:

    def __init__(
        self,
        workflow_service: ResearchWorkflowService,
        session_factory,
    ):
        self.workflow_service = (
            workflow_service
        )

        self.session_factory = (
            session_factory
        )

    def execute(
        self,
        context: ControlContext,
    ) -> ReportResult:

        if context.session_id is None:
            raise ValueError(
                "An active research session "
                "is required."
            )

        #
        # First inspect authoritative SQL state.
        #

        with self.session_factory() as db:

            session_repository = (
                ResearchSessionRepository(db)
            )

            report_repository = (
                ReportRepository(db)
            )

            research_session = (
                session_repository.get(
                    context.session_id
                )
            )

            if research_session is None:
                raise ValueError(
                    "Research session not found."
                )

            #
            # A completed session should already have
            # its durable final report.
            #
            # Never invoke the LLM merely because the
            # user asks for the report again.
            #

            if (
                research_session.status
                == "completed"
            ):

                report = (
                    report_repository
                    .get_for_session(
                        context.session_id
                    )
                )

                if report is None:
                    raise ValueError(
                        "The research session is "
                        "completed but its report "
                        "could not be found."
                    )

                return self._create_result(
                    report
                )

        #
        # The report does not yet exist.
        #
        # Resume the workflow. The durable session
        # status determines that LangGraph enters
        # the reporting phase.
        #

        self.workflow_service.resume(
            session_id=context.session_id,
        )

        #
        # Reload from SQL after workflow execution.
        #

        with self.session_factory() as db:

            report_repository = (
                ReportRepository(db)
            )

            report = (
                report_repository.get_for_session(
                    context.session_id
                )
            )

            if report is None:
                raise ValueError(
                    "Report generation completed "
                    "without producing a "
                    "persisted report."
                )

            return self._create_result(
                report
            )

    @staticmethod
    def _create_result(
        report,
    ) -> ReportResult:

        return ReportResult(
            report_id=report.id,
            session_id=(
                report.research_session_id
            ),
            title=report.title,
            executive_summary=(
                report.executive_summary
            ),
            conclusions=report.conclusions,
            limitations=list(
                report.limitations
            ),
        )