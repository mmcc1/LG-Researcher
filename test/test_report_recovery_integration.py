
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

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from sqlalchemy import (
    delete,
    select,
)

from application.report_file_writer import ReportFileWriter

from application.research_recovery_service import (
    ResearchRecoveryService,
)

from application.research_recovery_worker import (
    ResearchRecoveryWorker,
)

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from graph.state import ResearchState

from nodes.complete_report import CompleteReportNode
from nodes.generate_report import GenerateReportNode
from nodes.select_resume_phase import SelectResumePhaseNode

from persistence.database import SessionLocal

from persistence.models import (
    ResearchReportEntity,
    ReportLimitation,
    ReportSectionClaim,
    ReportSectionEntity,
    ResearchSession,
)

from persistence.report_repository import ReportRepository

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


TEST_TOPIC = "Disposable report recovery integration test"


class ForbiddenModelOperation:

    def __getattr__(
        self,
        name: str,
    ):

        raise AssertionError(
            "Recovery attempted to access a "
            f"model-dependent operation: {name}"
        )


def create_test_session() -> str:

    with SessionLocal() as db:

        repository = ResearchSessionRepository(
            db
        )

        research_session = repository.create(
            topic=TEST_TOPIC,
            scope="Persisted report recovery verification",
        )

        return research_session.id


def prepare_test_session(
    session_id: str,
) -> None:

    with SessionLocal() as db:

        research_session = db.get(
            ResearchSession,
            session_id,
        )

        assert research_session is not None
        assert research_session.status == "created"

        research_session.status = "reporting"

        research_session.updated_at = datetime.now(
            timezone.utc
        )

        db.commit()


def persist_test_report(
    session_id: str,
) -> int:

    with SessionLocal() as db:

        try:

            report = ResearchReportEntity(
                research_session_id=session_id,
                title="Recovered report integration test",
                executive_summary=(
                    "This is a disposable test report."
                ),
                conclusions=(
                    "The recovery workflow must reuse "
                    "this persisted report."
                ),
                created_at=datetime.now(
                    timezone.utc
                ),
            )

            db.add(
                report
            )

            db.flush()

            section = ReportSectionEntity(
                research_report_id=report.id,
                ordinal=1,
                heading="Recovery verification",
                content=(
                    "This section was persisted before "
                    "the recovery workflow started."
                ),
            )

            db.add(
                section
            )

            db.commit()

            return report.id

        except Exception:

            db.rollback()

            raise


def build_test_graph(
    output_directory: Path,
):

    select_resume_phase = SelectResumePhaseNode(
        session_factory=SessionLocal
    )

    generate_report = GenerateReportNode.__new__(
        GenerateReportNode
    )

    generate_report.session_factory = SessionLocal

    forbidden_operation = ForbiddenModelOperation()

    generate_report.report_agent = forbidden_operation
    generate_report.report_section_agent = forbidden_operation
    generate_report.report_synthesis_agent = forbidden_operation
    generate_report.context_builder = forbidden_operation
    generate_report.section_context_builder = forbidden_operation
    generate_report.validator = forbidden_operation
    generate_report.report_assembler = forbidden_operation

    complete_report = CompleteReportNode(
        session_factory=SessionLocal
    )

    complete_report.report_file_writer = ReportFileWriter(
        output_directory=output_directory
    )

    builder = StateGraph(
        ResearchState
    )

    builder.add_node(
        "select_resume_phase",
        select_resume_phase,
    )

    builder.add_node(
        "generate_report",
        generate_report,
    )

    builder.add_node(
        "complete_report",
        complete_report,
    )

    builder.add_edge(
        START,
        "select_resume_phase",
    )

    builder.add_edge(
        "select_resume_phase",
        "generate_report",
    )

    builder.add_edge(
        "generate_report",
        "complete_report",
    )

    builder.add_edge(
        "complete_report",
        END,
    )

    return builder.compile()


def get_session_status(
    session_id: str,
) -> str:

    with SessionLocal() as db:

        research_session = db.get(
            ResearchSession,
            session_id,
        )

        assert research_session is not None

        return research_session.status


def verify_report(
    session_id: str,
    expected_report_id: int,
) -> None:

    with SessionLocal() as db:

        repository = ReportRepository(
            db
        )

        report = repository.get_for_session(
            session_id
        )

        assert report is not None
        assert report.id == expected_report_id

        assert report.title == (
            "Recovered report integration test"
        )

        assert len(
            report.sections
        ) == 1

        assert report.sections[0].reviewed_claim_ids == []

        report_ids = db.execute(
            select(
                ResearchReportEntity.id
            ).where(
                ResearchReportEntity.research_session_id
                == session_id
            )
        ).scalars().all()

        assert report_ids == [
            expected_report_id
        ]


def verify_export(
    session_id: str,
    output_directory: Path,
) -> None:

    report_path = (
        output_directory
        / f"{session_id}.txt"
    )

    assert report_path.is_file()

    report_text = report_path.read_text(
        encoding="utf-8"
    )

    assert (
        "Recovered report integration test"
        in report_text
    )

    assert (
        "This section was persisted before"
        in report_text
    )

    assert (
        "The recovery workflow must reuse"
        in report_text
    )


def cleanup_test_session(
    session_id: str,
) -> None:

    with SessionLocal() as db:

        try:

            research_session = db.get(
                ResearchSession,
                session_id,
            )

            if research_session is None:

                return

            if research_session.topic != TEST_TOPIC:

                raise RuntimeError(
                    "Cleanup refused: unexpected "
                    "research session topic."
                )

            report_ids = db.execute(
                select(
                    ResearchReportEntity.id
                ).where(
                    ResearchReportEntity.research_session_id
                    == session_id
                )
            ).scalars().all()

            if report_ids:

                section_ids = db.execute(
                    select(
                        ReportSectionEntity.id
                    ).where(
                        ReportSectionEntity.research_report_id.in_(
                            report_ids
                        )
                    )
                ).scalars().all()

                if section_ids:

                    db.execute(
                        delete(
                            ReportSectionClaim
                        ).where(
                            ReportSectionClaim.report_section_id.in_(
                                section_ids
                            )
                        )
                    )

                db.execute(
                    delete(
                        ReportSectionEntity
                    ).where(
                        ReportSectionEntity.research_report_id.in_(
                            report_ids
                        )
                    )
                )

                db.execute(
                    delete(
                        ReportLimitation
                    ).where(
                        ReportLimitation.research_report_id.in_(
                            report_ids
                        )
                    )
                )

                db.execute(
                    delete(
                        ResearchReportEntity
                    ).where(
                        ResearchReportEntity.id.in_(
                            report_ids
                        )
                    )
                )

            db.delete(
                research_session
            )

            db.commit()

        except Exception:

            db.rollback()

            raise


def main():

    print()
    print(
        "REPORT RECOVERY INTEGRATION TEST"
    )

    session_id = create_test_session()

    print()
    print(
        f"Disposable session: {session_id}"
    )

    try:

        prepare_test_session(
            session_id
        )

        report_id = persist_test_report(
            session_id
        )

        assert get_session_status(
            session_id
        ) == "reporting"

        print(
            "Reporting session and persisted report: PASSED"
        )

        with TemporaryDirectory(
            prefix="lgresearcher-recovery-test-"
        ) as temporary_directory:

            output_directory = Path(
                temporary_directory
            )

            graph = build_test_graph(
                output_directory=output_directory
            )

            workflow_service = ResearchWorkflowService(
                graph=graph,
                session_factory=SessionLocal,
                lease_duration_seconds=120,
                heartbeat_interval_seconds=30.0,
            )

            recovery_service = ResearchRecoveryService(
                workflow_service=workflow_service,
                session_factory=SessionLocal,
            )

            recovery_worker = ResearchRecoveryWorker(
                recovery_service=recovery_service,
            )

            summary = recovery_worker.run_session(
                session_id
            )

            assert summary.scanned == 1
            assert summary.resumed == 1
            assert summary.paused == 0
            assert summary.skipped == 0
            assert summary.failed == 0

            print(
                "Targeted recovery worker execution: PASSED"
            )

            assert get_session_status(
                session_id
            ) == "completed"

            print(
                "Database session completion: PASSED"
            )

            verify_report(
                session_id=session_id,
                expected_report_id=report_id,
            )

            print(
                "Persisted report reused without duplication: PASSED"
            )

            verify_export(
                session_id=session_id,
                output_directory=output_directory,
            )

            print(
                "Report file exported: PASSED"
            )

            with SessionLocal() as db:

                research_session = db.get(
                    ResearchSession,
                    session_id,
                )

                assert research_session is not None

                assert research_session.execution_owner is None

                assert (
                    research_session.execution_lease_expires_at
                    is None
                )

            print(
                "Execution lease released: PASSED"
            )

        print(
            "Temporary export directory cleanup: PASSED"
        )

    finally:

        cleanup_test_session(
            session_id
        )

        print(
            "Disposable database cleanup: PASSED"
        )

    print()
    print(
        "Report recovery integration: PASSED"
    )


if __name__ == "__main__":

    main()
