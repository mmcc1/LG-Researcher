
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

from sqlalchemy import delete, select

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import (
    ResearchReportEntity,
    ReportSectionEntity,
    ReportSectionClaim,
    ReportLimitation,
    ResearchSession,
)

from persistence.report_repository import ReportRepository

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


TEST_TOPIC = "Disposable fenced report completion test"


def create_test_session() -> str:

    with SessionLocal() as db:

        repository = ResearchSessionRepository(
            db
        )

        research_session = repository.create(
            topic=TEST_TOPIC,
            scope="Database-backed completion verification",
        )

        return research_session.id


def set_reporting_status(
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


def acquire_lease(
    session_id: str,
) -> ExecutionLease:

    with SessionLocal() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        return repository.acquire(
            session_id=session_id,
            duration_seconds=120,
        )


def release_lease(
    lease: ExecutionLease,
) -> bool:

    with SessionLocal() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        return repository.release(
            lease
        )


def get_status(
    session_id: str,
) -> str:

    with SessionLocal() as db:

        research_session = db.get(
            ResearchSession,
            session_id,
        )

        assert research_session is not None

        return research_session.status


def get_report_count(
    session_id: str,
) -> int:

    with SessionLocal() as db:

        statement = select(
            ResearchReportEntity.id
        ).where(
            ResearchReportEntity.research_session_id
            == session_id
        )

        report_ids = db.execute(
            statement
        ).scalars().all()

        return len(
            report_ids
        )


def insert_test_report(
    session_id: str,
) -> int:

    with SessionLocal() as db:

        try:

            report = ResearchReportEntity(
                research_session_id=session_id,
                title="Disposable completion test report",
                executive_summary=(
                    "Synthetic fixture for persistence testing."
                ),
                conclusions=(
                    "This report contains no research findings."
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
                heading="Test section",
                content=(
                    "This section verifies persisted "
                    "report completion."
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


def complete_report(
    session_id: str,
    lease: ExecutionLease,
) -> None:

    with SessionLocal() as db:

        repository = ResearchSessionRepository(
            db
        )

        repository.complete_report_fenced(
            session_id=session_id,
            lease=lease,
        )


def assert_completion_rejected(
    session_id: str,
    lease: ExecutionLease,
    expected_exception: type[Exception],
) -> None:

    try:

        complete_report(
            session_id=session_id,
            lease=lease,
        )

    except expected_exception:

        return

    raise AssertionError(
        "Report completion unexpectedly succeeded."
    )


def verify_persisted_report(
    session_id: str,
) -> None:

    with SessionLocal() as db:

        repository = ReportRepository(
            db
        )

        report = repository.get_for_session(
            session_id
        )

        assert report is not None

        assert report.title == (
            "Disposable completion test report"
        )

        assert len(
            report.sections
        ) == 1

        assert report.sections[0].heading == (
            "Test section"
        )

        assert report.sections[0].reviewed_claim_ids == []


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
                    "Cleanup refused: session topic "
                    "does not match the test fixture."
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

    session_id = create_test_session()

    print()
    print(
        "DATABASE-BACKED REPORT COMPLETION TEST"
    )

    print()
    print(
        f"Disposable session: {session_id}"
    )

    try:

        set_reporting_status(
            session_id
        )

        first_lease = acquire_lease(
            session_id
        )

        assert_completion_rejected(
            session_id=session_id,
            lease=first_lease,
            expected_exception=RuntimeError,
        )

        assert get_status(
            session_id
        ) == "reporting"

        print(
            "Completion without persisted report rejected: PASSED"
        )

        report_id = insert_test_report(
            session_id
        )

        assert report_id > 0

        verify_persisted_report(
            session_id
        )

        print(
            "Persisted report fixture: PASSED"
        )

        released = release_lease(
            first_lease
        )

        assert released

        second_lease = acquire_lease(
            session_id
        )

        assert (
            second_lease.version
            == first_lease.version + 1
        )

        assert_completion_rejected(
            session_id=session_id,
            lease=first_lease,
            expected_exception=ExecutionLeaseFenceRejected,
        )

        assert get_status(
            session_id
        ) == "reporting"

        print(
            "Stale lease completion rejected: PASSED"
        )

        complete_report(
            session_id=session_id,
            lease=second_lease,
        )

        assert get_status(
            session_id
        ) == "completed"

        print(
            "Valid fenced completion: PASSED"
        )

        complete_report(
            session_id=session_id,
            lease=second_lease,
        )

        assert get_status(
            session_id
        ) == "completed"

        assert get_report_count(
            session_id
        ) == 1

        print(
            "Idempotent completion: PASSED"
        )

        released = release_lease(
            second_lease
        )

        assert released

        assert_completion_rejected(
            session_id=session_id,
            lease=second_lease,
            expected_exception=ExecutionLeaseFenceRejected,
        )

        assert get_status(
            session_id
        ) == "completed"

        print(
            "Released lease completion rejected: PASSED"
        )

        assert get_report_count(
            session_id
        ) == 1

        print(
            "No duplicate report created: PASSED"
        )

    finally:

        cleanup_test_session(
            session_id
        )

        print(
            "Disposable session cleanup: PASSED"
        )

    print()
    print(
        "Database-backed report completion: PASSED"
    )


if __name__ == "__main__":

    main()
