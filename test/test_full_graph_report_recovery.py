
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
from unittest.mock import MagicMock, patch

from sqlalchemy import delete, select

from application.report_file_writer import ReportFileWriter
from application.research_recovery_service import ResearchRecoveryService
from application.research_recovery_worker import ResearchRecoveryWorker
from application.research_workflow_service import ResearchWorkflowService

from graph.research_graph import create_research_graph

from models.agent_models import AgentModels

from nodes.complete_report import CompleteReportNode
from nodes.generate_report import GenerateReportNode

from persistence.database import SessionLocal

from persistence.models import (
    ResearchReportEntity,
    ReportLimitation,
    ReportSectionClaim,
    ReportSectionEntity,
    ResearchSession,
)

from persistence.report_repository import ReportRepository
from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
)
from persistence.research_session_repository import ResearchSessionRepository


TEST_TOPIC = "Disposable full graph recovery test"


def forbidden_operation(*args, **kwargs):

    raise AssertionError(
        "Recovery attempted an LLM or network operation."
    )


def create_test_session(
    pause_requested: bool = False,
) -> tuple[str, int]:

    with SessionLocal() as db:

        repository = ResearchSessionRepository(db)

        research_session = repository.create(
            topic=TEST_TOPIC,
            scope="Full production graph recovery verification",
        )

        session_id = research_session.id

    with SessionLocal() as db:

        try:

            research_session = db.get(
                ResearchSession,
                session_id,
            )

            assert research_session is not None

            research_session.status = "reporting"
            research_session.pause_requested = pause_requested

            research_session.updated_at = datetime.now(
                timezone.utc
            )

            report = ResearchReportEntity(
                research_session_id=session_id,
                title="Full graph recovery test report",
                executive_summary=(
                    "Synthetic report for recovery verification."
                ),
                conclusions=(
                    "The persisted report must be reused."
                ),
                created_at=datetime.now(
                    timezone.utc
                ),
            )

            db.add(report)
            db.flush()

            section = ReportSectionEntity(
                research_report_id=report.id,
                ordinal=1,
                heading="Recovery verification",
                content=(
                    "This content was persisted before "
                    "the recovery worker started."
                ),
            )

            db.add(section)
            db.commit()

            return session_id, report.id

        except Exception:

            db.rollback()
            raise


def build_test_models() -> AgentModels:

    model = MagicMock(
        name="ForbiddenLLM"
    )

    model.invoke.side_effect = forbidden_operation
    model.ainvoke.side_effect = forbidden_operation
    model.stream.side_effect = forbidden_operation
    model.astream.side_effect = forbidden_operation
    model.batch.side_effect = forbidden_operation
    model.abatch.side_effect = forbidden_operation

    return AgentModels(
        planner=model,
        researcher=model,
        summariser=model,
        reviewer=model,
        reporter=model,
        controller=model,
    )


def build_test_worker(
    output_directory: Path,
) -> ResearchRecoveryWorker:

    models = build_test_models()

    search_provider = MagicMock(
        name="ForbiddenSearchProvider"
    )

    search_provider.search.side_effect = forbidden_operation

    document_retriever = MagicMock(
        name="ForbiddenDocumentRetriever"
    )

    document_retriever.retrieve.side_effect = forbidden_operation

    document_extractor = MagicMock(
        name="ForbiddenDocumentExtractor"
    )

    document_extractor.extract.side_effect = forbidden_operation

    original_complete_report = CompleteReportNode

    def create_test_complete_report(
        session_factory,
    ):

        node = original_complete_report(
            session_factory=session_factory
        )

        node.report_file_writer = ReportFileWriter(
            output_directory=output_directory
        )

        return node

    with patch(
        "graph.research_graph.CompleteReportNode",
        side_effect=create_test_complete_report,
    ):

        graph = create_research_graph(
            models=models,
            session_factory=SessionLocal,
            search_provider=search_provider,
            document_retriever=document_retriever,
            document_extractor=document_extractor,
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

    return ResearchRecoveryWorker(
        recovery_service=recovery_service
    )


def get_session(
    session_id: str,
) -> tuple[str, str | None, datetime | None]:

    with SessionLocal() as db:

        research_session = db.get(
            ResearchSession,
            session_id,
        )

        assert research_session is not None

        return (
            research_session.status,
            research_session.execution_owner,
            research_session.execution_lease_expires_at,
        )


def verify_report(
    session_id: str,
    report_id: int,
) -> None:

    with SessionLocal() as db:

        repository = ReportRepository(db)

        report = repository.get_for_session(
            session_id
        )

        assert report is not None
        assert report.id == report_id

        assert report.title == (
            "Full graph recovery test report"
        )

        assert len(report.sections) == 1

        assert (
            report.sections[0].reviewed_claim_ids
            == []
        )

        report_ids = db.execute(
            select(
                ResearchReportEntity.id
            ).where(
                ResearchReportEntity.research_session_id
                == session_id
            )
        ).scalars().all()

        assert report_ids == [report_id]


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
        "Full graph recovery test report"
        in report_text
    )

    assert (
        "This content was persisted before"
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
                    "Cleanup refused: unexpected session topic."
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

            db.delete(research_session)
            db.commit()

        except Exception:

            db.rollback()
            raise


def test_successful_recovery(
    worker: ResearchRecoveryWorker,
    output_directory: Path,
) -> None:

    session_id = None

    try:

        session_id, report_id = create_test_session()

        print()
        print(
            f"Reporting session: {session_id}"
        )

        summary = worker.run_session(
            session_id
        )

        assert summary.scanned == 1
        assert summary.resumed == 1
        assert summary.paused == 0
        assert summary.skipped == 0
        assert summary.failed == 0

        print(
            "Production graph recovery: PASSED"
        )

        status, owner, expires_at = get_session(
            session_id
        )

        assert status == "completed"

        print(
            "Session completion: PASSED"
        )

        verify_report(
            session_id=session_id,
            report_id=report_id,
        )

        print(
            "Persisted report reused: PASSED"
        )

        verify_export(
            session_id=session_id,
            output_directory=output_directory,
        )

        print(
            "Report file export: PASSED"
        )

        assert owner is None
        assert expires_at is None

        print(
            "Execution lease released: PASSED"
        )

    finally:

        if session_id is not None:

            cleanup_test_session(
                session_id
            )

            print(
                "Completed session cleanup: PASSED"
            )


def test_paused_recovery(
    worker: ResearchRecoveryWorker,
    output_directory: Path,
) -> None:

    session_id = None

    try:

        session_id, report_id = create_test_session(
            pause_requested=True
        )

        print()
        print(
            f"Pause-requested session: {session_id}"
        )

        summary = worker.run_session(
            session_id
        )

        assert summary.scanned == 1
        assert summary.resumed == 0
        assert summary.paused == 0
        assert summary.skipped == 1
        assert summary.failed == 0

        print(
            "Pause-requested recovery rejected: PASSED"
        )

        status, owner, expires_at = get_session(
            session_id
        )

        assert status == "reporting"
        assert owner is None
        assert expires_at is None

        print(
            "Paused session state preserved: PASSED"
        )

        verify_report(
            session_id=session_id,
            report_id=report_id,
        )

        report_path = (
            output_directory
            / f"{session_id}.txt"
        )

        assert not report_path.exists()

        print(
            "No report exported for skipped session: PASSED"
        )

    finally:

        if session_id is not None:

            cleanup_test_session(
                session_id
            )

            print(
                "Skipped session cleanup: PASSED"
            )



def test_interrupted_report_completion(
    worker: ResearchRecoveryWorker,
    output_directory: Path,
) -> None:

    session_id = None

    try:

        session_id, report_id = create_test_session()

        print()
        print(
            f"Interrupted completion session: {session_id}"
        )

        report_path = (
            output_directory
            / f"{session_id}.txt"
        )

        assert not report_path.exists()

        original_complete_report_fenced = (
            ResearchSessionRepository.complete_report_fenced
        )

        completion_attempts = 0

        def interrupt_completion(
            repository,
            session_id,
            lease,
        ):

            nonlocal completion_attempts

            completion_attempts += 1

            if completion_attempts == 1:

                assert report_path.is_file()

                assert (
                    repository.get(session_id).status
                    == "reporting"
                )

                raise RuntimeError(
                    "Simulated interruption after "
                    "report export."
                )

            return original_complete_report_fenced(
                repository,
                session_id=session_id,
                lease=lease,
            )

        with patch.object(
            ResearchSessionRepository,
            "complete_report_fenced",
            new=interrupt_completion,
        ):

            first_summary = worker.run_session(
                session_id
            )

        assert completion_attempts == 1

        assert first_summary.scanned == 1
        assert first_summary.resumed == 0
        assert first_summary.paused == 0
        assert first_summary.skipped == 0
        assert first_summary.failed == 1

        assert len(first_summary.outcomes) == 1

        assert (
            "Simulated interruption after report export."
            in first_summary.outcomes[0].error
        )

        print(
            "Controlled completion failure: PASSED"
        )

        status, owner, expires_at = get_session(
            session_id
        )

        assert status == "reporting"
        assert owner is None
        assert expires_at is None

        print(
            "Reporting state and lease cleanup: PASSED"
        )

        verify_report(
            session_id=session_id,
            report_id=report_id,
        )

        verify_export(
            session_id=session_id,
            output_directory=output_directory,
        )

        first_report_text = report_path.read_text(
            encoding="utf-8"
        )

        first_modified_time = report_path.stat().st_mtime_ns

        print(
            "Report persisted and exported before failure: PASSED"
        )

        second_summary = worker.run_session(
            session_id
        )

        assert second_summary.scanned == 1
        assert second_summary.resumed == 1
        assert second_summary.paused == 0
        assert second_summary.skipped == 0
        assert second_summary.failed == 0

        print(
            "Recovery after interrupted completion: PASSED"
        )

        status, owner, expires_at = get_session(
            session_id
        )

        assert status == "completed"
        assert owner is None
        assert expires_at is None

        print(
            "Fenced completion and lease release: PASSED"
        )

        verify_report(
            session_id=session_id,
            report_id=report_id,
        )

        print(
            "Persisted report reused without duplication: PASSED"
        )

        verify_export(
            session_id=session_id,
            output_directory=output_directory,
        )

        second_report_text = report_path.read_text(
            encoding="utf-8"
        )

        second_modified_time = report_path.stat().st_mtime_ns

        assert second_report_text == first_report_text

        assert second_modified_time >= first_modified_time

        temporary_files = list(
            output_directory.glob(
                f"*{session_id}*.tmp"
            )
        )

        assert temporary_files == []

        print(
            "Report file safely rewritten: PASSED"
        )

    finally:

        if session_id is not None:

            cleanup_test_session(
                session_id
            )

            print(
                "Interrupted session cleanup: PASSED"
            )



def test_pause_during_execution(
    worker: ResearchRecoveryWorker,
    output_directory: Path,
) -> None:

    session_id = None

    try:

        session_id, report_id = create_test_session()

        print()
        print(
            f"Mid-execution pause session: {session_id}"
        )

        report_path = (
            output_directory
            / f"{session_id}.txt"
        )

        assert not report_path.exists()

        original_generate_report_call = (
            GenerateReportNode.__call__
        )

        pause_injected = False

        def generate_report_and_request_pause(
            node,
            state,
            config,
        ):

            nonlocal pause_injected

            result = original_generate_report_call(
                node,
                state,
                config,
            )

            if (
                state["session_id"] == session_id
                and not pause_injected
            ):

                with SessionLocal() as db:

                    research_session = db.get(
                        ResearchSession,
                        session_id,
                    )

                    assert research_session is not None

                    assert research_session.status == "reporting"

                    research_session.pause_requested = True

                    db.commit()

                pause_injected = True

                print(
                    "Pause requested after report generation."
                )

            return result

        with patch.object(
            GenerateReportNode,
            "__call__",
            new=generate_report_and_request_pause,
        ):

            first_summary = worker.run_session(
                session_id
            )

        assert pause_injected

        assert first_summary.scanned == 1
        assert first_summary.resumed == 0
        assert first_summary.paused == 1
        assert first_summary.skipped == 0
        assert first_summary.failed == 0

        print(
            "Mid-execution pause detected: PASSED"
        )

        status, owner, expires_at = get_session(
            session_id
        )

        assert status == "reporting"
        assert owner is None
        assert expires_at is None

        print(
            "Reporting state and lease preserved: PASSED"
        )

        verify_report(
            session_id=session_id,
            report_id=report_id,
        )

        assert not report_path.exists()

        print(
            "Report completion prevented by pause: PASSED"
        )

        with SessionLocal() as db:

            research_session = db.get(
                ResearchSession,
                session_id,
            )

            assert research_session is not None
            assert research_session.pause_requested is True

            research_session.pause_requested = False

            db.commit()

        print(
            "Pause request cleared: PASSED"
        )

        second_summary = worker.run_session(
            session_id
        )

        assert second_summary.scanned == 1
        assert second_summary.resumed == 1
        assert second_summary.paused == 0
        assert second_summary.skipped == 0
        assert second_summary.failed == 0

        print(
            "Recovery after pause: PASSED"
        )

        status, owner, expires_at = get_session(
            session_id
        )

        assert status == "completed"
        assert owner is None
        assert expires_at is None

        verify_report(
            session_id=session_id,
            report_id=report_id,
        )

        verify_export(
            session_id=session_id,
            output_directory=output_directory,
        )

        print(
            "Report completed after pause cleared: PASSED"
        )

    finally:

        if session_id is not None:

            cleanup_test_session(
                session_id
            )

            print(
                "Mid-execution pause session cleanup: PASSED"
            )


def main():

    print()
    print(
        "FULL PRODUCTION GRAPH REPORT RECOVERY TEST"
    )

    with TemporaryDirectory(
        prefix="lgresearcher-full-graph-test-"
    ) as temporary_directory:

        output_directory = Path(
            temporary_directory
        )

        worker = build_test_worker(
            output_directory=output_directory
        )

        print(
            "Production graph constructed: PASSED"
        )

        test_successful_recovery(
            worker=worker,
            output_directory=output_directory,
        )

        test_paused_recovery(
            worker=worker,
            output_directory=output_directory,
        )

        test_interrupted_report_completion(
            worker=worker,
            output_directory=output_directory,
        )

        test_pause_during_execution(
            worker=worker,
            output_directory=output_directory,
        )

    print()
    print(
        "Temporary export directory cleanup: PASSED"
    )

    print()
    print(
        "Full production graph report recovery: PASSED"
    )


if __name__ == "__main__":

    main()
