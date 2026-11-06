
import os

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

import pytest

from sqlalchemy import (
    text,
)

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseFenceRejected,
)

from persistence.report_repository import (
    ReportRepository,
)

from domain.report import (
    ResearchReport,
    ReportSection,
)

from sqlalchemy import event

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from sqlalchemy.exc import DBAPIError


pytestmark = pytest.mark.skipif(
    os.environ.get(
        "RUN_SQLSERVER_INTEGRATION_TESTS"
    ) != "1",
    reason=(
        "SQL Server integration tests are disabled."
    ),
)


@pytest.fixture
def reporting_session_id():

    session_id = str(
        uuid4()
    )

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    with SessionLocal() as db:

        db.execute(
            text(
                """
                INSERT INTO dbo.research_sessions (
                    id,
                    topic,
                    status,
                    pause_requested,
                    created_at,
                    updated_at
                )
                VALUES (
                    :session_id,
                    :topic,
                    :status,
                    :pause_requested,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "session_id": session_id,
                "topic": (
                    "Report persistence integration test"
                ),
                "status": "reporting",
                "pause_requested": False,
                "created_at": now,
                "updated_at": now,
            },
        )

        db.commit()

    try:

        yield session_id

    finally:

        with SessionLocal() as db:

            db.execute(
                text(
                    """
                    DELETE FROM dbo.report_section_claims
                    WHERE report_section_id IN (
                        SELECT rs.id
                        FROM dbo.report_sections AS rs
                        INNER JOIN dbo.research_reports AS rr
                            ON rr.id = rs.research_report_id
                        WHERE rr.research_session_id = :session_id
                    )
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.report_sections
                    WHERE research_report_id IN (
                        SELECT id
                        FROM dbo.research_reports
                        WHERE research_session_id = :session_id
                    )
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.report_limitations
                    WHERE research_report_id IN (
                        SELECT id
                        FROM dbo.research_reports
                        WHERE research_session_id = :session_id
                    )
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.research_reports
                    WHERE research_session_id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.reviewed_claims
                    WHERE question_review_id IN (
                        SELECT qr.id
                        FROM dbo.question_reviews AS qr
                        INNER JOIN dbo.research_questions AS rq
                            ON rq.id = qr.research_question_id
                        WHERE rq.research_session_id = :session_id
                    )
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.question_reviews
                    WHERE research_question_id IN (
                        SELECT id
                        FROM dbo.research_questions
                        WHERE research_session_id = :session_id
                    )
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.research_questions
                    WHERE research_session_id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.research_sessions
                    WHERE id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            db.commit()


def test_superseded_lease_cannot_persist_report(
    reporting_session_id,
):

    session_id = reporting_session_id

    with SessionLocal() as db:

        first_lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    with SessionLocal() as db:

        db.execute(
            text(
                """
                UPDATE dbo.research_sessions
                SET execution_lease_expires_at =
                    DATEADD(
                        second,
                        -1,
                        SYSUTCDATETIME()
                    )
                WHERE id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        )

        db.commit()

    with SessionLocal() as db:

        second_lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    assert second_lease.version > first_lease.version

    with SessionLocal() as db:

        repository = ReportRepository(
            db
        )

        with pytest.raises(
            ExecutionLeaseFenceRejected
        ):

            repository.save_report_fenced(
                session_id=session_id,
                report=None,
                lease=first_lease,
            )

    with SessionLocal() as db:

        report_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM dbo.research_reports
                WHERE research_session_id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

    assert report_count == 0



def create_reviewed_claim(
    session_id: str,
) -> int:

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    with SessionLocal() as db:

        question_id = db.execute(
            text(
                """
                INSERT INTO dbo.research_questions (
                    research_session_id,
                    category,
                    question,
                    rationale,
                    status,
                    created_at,
                    updated_at
                )
                OUTPUT INSERTED.id
                VALUES (
                    :session_id,
                    :category,
                    :question,
                    :rationale,
                    :status,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "session_id": session_id,
                "category": "Integration test",
                "question": "What does the evidence establish?",
                "rationale": "Test report provenance.",
                "status": "completed",
                "created_at": now,
                "updated_at": now,
            },
        ).scalar_one()

        review_id = db.execute(
            text(
                """
                INSERT INTO dbo.question_reviews (
                    research_question_id,
                    answer,
                    overall_confidence,
                    sufficient_evidence,
                    created_at
                )
                OUTPUT INSERTED.id
                VALUES (
                    :question_id,
                    :answer,
                    :confidence,
                    :sufficient_evidence,
                    :created_at
                )
                """
            ),
            {
                "question_id": question_id,
                "answer": "The evidence supports the claim.",
                "confidence": "high",
                "sufficient_evidence": True,
                "created_at": now,
            },
        ).scalar_one()

        claim_id = db.execute(
            text(
                """
                INSERT INTO dbo.reviewed_claims (
                    question_review_id,
                    claim,
                    confidence
                )
                OUTPUT INSERTED.id
                VALUES (
                    :review_id,
                    :claim,
                    :confidence
                )
                """
            ),
            {
                "review_id": review_id,
                "claim": "A verified integration-test claim.",
                "confidence": "high",
            },
        ).scalar_one()

        db.commit()

    return claim_id


def build_test_report(
    claim_id: int,
) -> ResearchReport:

    return ResearchReport(
        title="Integration Test Report",
        executive_summary=(
            "The reviewed evidence supports "
            "the principal finding."
        ),
        sections=[
            ReportSection(
                heading="Principal Finding",
                content=(
                    "The reviewed evidence supports "
                    "this finding."
                ),
                reviewed_claim_ids=[
                    claim_id,
                ],
            ),
        ],
        conclusions=(
            "The evidence supports the conclusion."
        ),
        limitations=[
            "The available evidence is limited.",
        ],
    )


def test_valid_report_is_persisted(
    reporting_session_id,
):

    session_id = reporting_session_id

    claim_id = create_reviewed_claim(
        session_id
    )

    report = build_test_report(
        claim_id
    )

    with SessionLocal() as db:

        lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    with SessionLocal() as db:

        repository = ReportRepository(
            db
        )

        report_id = repository.save_report_fenced(
            session_id=session_id,
            report=report,
            lease=lease,
        )

    with SessionLocal() as db:

        persisted = ReportRepository(
            db
        ).get_for_session(
            session_id
        )

    assert persisted is not None

    assert persisted.id == report_id

    assert persisted.title == report.title

    assert len(persisted.sections) == 1

    assert persisted.sections[0].reviewed_claim_ids == [
        claim_id,
    ]

    assert persisted.limitations == report.limitations


def test_report_persistence_is_idempotent(
    reporting_session_id,
):

    session_id = reporting_session_id

    claim_id = create_reviewed_claim(
        session_id
    )

    report = build_test_report(
        claim_id
    )

    with SessionLocal() as db:

        lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    with SessionLocal() as db:

        repository = ReportRepository(
            db
        )

        first_report_id = repository.save_report_fenced(
            session_id=session_id,
            report=report,
            lease=lease,
        )

        second_report_id = repository.save_report_fenced(
            session_id=session_id,
            report=None,
            lease=lease,
        )

    assert first_report_id == second_report_id

    with SessionLocal() as db:

        report_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM dbo.research_reports
                WHERE research_session_id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

    assert report_count == 1


def test_foreign_reviewed_claim_is_rejected(
    reporting_session_id,
):

    session_id = reporting_session_id

    foreign_session_id = str(
        uuid4()
    )

    now = datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )

    with SessionLocal() as db:

        db.execute(
            text(
                """
                INSERT INTO dbo.research_sessions (
                    id,
                    topic,
                    status,
                    pause_requested,
                    created_at,
                    updated_at
                )
                VALUES (
                    :session_id,
                    :topic,
                    :status,
                    :pause_requested,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "session_id": foreign_session_id,
                "topic": "Foreign provenance test",
                "status": "reporting",
                "pause_requested": False,
                "created_at": now,
                "updated_at": now,
            },
        )

        db.commit()

    try:

        foreign_claim_id = create_reviewed_claim(
            foreign_session_id
        )

        report = build_test_report(
            foreign_claim_id
        )

        with SessionLocal() as db:

            lease = ExecutionLeaseRepository(
                db
            ).acquire(
                session_id=session_id,
                duration_seconds=120,
            )

        with SessionLocal() as db:

            repository = ReportRepository(
                db
            )

            with pytest.raises(
                ValueError,
                match="do not belong",
            ):

                repository.save_report_fenced(
                    session_id=session_id,
                    report=report,
                    lease=lease,
                )

        with SessionLocal() as db:

            report_count = db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM dbo.research_reports
                    WHERE research_session_id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            ).scalar_one()

        assert report_count == 0

    finally:

        with SessionLocal() as db:

            db.execute(
                text(
                    """
                    DELETE FROM dbo.reviewed_claims
                    WHERE question_review_id IN (
                        SELECT qr.id
                        FROM dbo.question_reviews AS qr
                        INNER JOIN dbo.research_questions AS rq
                            ON rq.id = qr.research_question_id
                        WHERE rq.research_session_id = :session_id
                    )
                    """
                ),
                {
                    "session_id": foreign_session_id,
                },
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.question_reviews
                    WHERE research_question_id IN (
                        SELECT id
                        FROM dbo.research_questions
                        WHERE research_session_id = :session_id
                    )
                    """
                ),
                {
                    "session_id": foreign_session_id,
                },
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.research_questions
                    WHERE research_session_id = :session_id
                    """
                ),
                {
                    "session_id": foreign_session_id,
                },
            )

            db.execute(
                text(
                    """
                    DELETE FROM dbo.research_sessions
                    WHERE id = :session_id
                    """
                ),
                {
                    "session_id": foreign_session_id,
                },
            )

            db.commit()


def test_failed_report_save_rolls_back(
    reporting_session_id,
):

    session_id = reporting_session_id

    claim_id = create_reviewed_claim(
        session_id
    )

    report = build_test_report(
        claim_id
    )

    report.sections.append(
        ReportSection(
            heading="Invalid Section",
            content="Unsupported claim reference.",
            reviewed_claim_ids=[
                -999999,
            ],
        )
    )

    with SessionLocal() as db:

        lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    with SessionLocal() as db:

        repository = ReportRepository(
            db
        )

        with pytest.raises(
            ValueError
        ):

            repository.save_report_fenced(
                session_id=session_id,
                report=report,
                lease=lease,
            )

    with SessionLocal() as db:

        report_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM dbo.research_reports
                WHERE research_session_id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

    assert report_count == 0



def test_partial_report_write_is_rolled_back(
    reporting_session_id,
):

    session_id = reporting_session_id

    claim_id = create_reviewed_claim(
        session_id
    )

    report = build_test_report(
        claim_id
    )

    report.sections.append(
        ReportSection(
            heading="Second Finding",
            content=(
                "Additional evidence supporting "
                "the research conclusions."
            ),
            reviewed_claim_ids=[
                claim_id,
            ],
        )
    )

    with SessionLocal() as db:

        lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=120,
        )

    inserted_section_count = 0

    def fail_on_second_section(
        conn,
        cursor,
        statement,
        parameters,
        context,
        executemany,
    ):

        nonlocal inserted_section_count

        normalized_statement = (
            statement.lower()
        )

        if (
            "insert into report_sections"
            not in normalized_statement
            and "insert into dbo.report_sections"
            not in normalized_statement
        ):

            return

        inserted_section_count += 1

        if inserted_section_count == 2:

            raise RuntimeError(
                "Injected failure during "
                "second report section insertion."
            )

    with SessionLocal() as db:

        repository = ReportRepository(
            db
        )

        connection = db.connection()

        event.listen(
            connection,
            "before_cursor_execute",
            fail_on_second_section,
        )

        try:

            with pytest.raises(
                RuntimeError,
                match="Injected failure",
            ):

                repository.save_report_fenced(
                    session_id=session_id,
                    report=report,
                    lease=lease,
                )

        finally:

            event.remove(
                connection,
                "before_cursor_execute",
                fail_on_second_section,
            )

    assert inserted_section_count == 2

    with SessionLocal() as db:

        report_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM dbo.research_reports
                WHERE research_session_id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

        section_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM dbo.report_sections AS rs
                INNER JOIN dbo.research_reports AS rr
                    ON rr.id = rs.research_report_id
                WHERE rr.research_session_id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

        limitation_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM dbo.report_limitations AS rl
                INNER JOIN dbo.research_reports AS rr
                    ON rr.id = rl.research_report_id
                WHERE rr.research_session_id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

    assert report_count == 0

    assert section_count == 0

    assert limitation_count == 0



def test_report_transaction_blocks_competing_writer(
    reporting_session_id,
):

    session_id = reporting_session_id

    claim_id = create_reviewed_claim(
        session_id
    )

    report = build_test_report(
        claim_id
    )

    with SessionLocal() as db:

        first_lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id=session_id,
            duration_seconds=2,
        )

    header_inserted = Event()

    allow_first_worker_to_finish = Event()

    def first_worker():

        def pause_after_report_header(
            conn,
            cursor,
            statement,
            parameters,
            context,
            executemany,
        ):

            normalized_statement = (
                statement.lower()
            )

            if (
                "insert into research_reports"
                not in normalized_statement
                and "insert into dbo.research_reports"
                not in normalized_statement
            ):

                return

            header_inserted.set()

            if not allow_first_worker_to_finish.wait(
                timeout=15
            ):

                raise RuntimeError(
                    "Timed out waiting to resume "
                    "the first report writer."
                )

        with SessionLocal() as db:

            connection = db.connection()

            event.listen(
                connection,
                "after_cursor_execute",
                pause_after_report_header,
            )

            try:

                repository = ReportRepository(
                    db
                )

                return repository.save_report_fenced(
                    session_id=session_id,
                    report=report,
                    lease=first_lease,
                )

            finally:

                event.remove(
                    connection,
                    "after_cursor_execute",
                    pause_after_report_header,
                )

    with ThreadPoolExecutor(
        max_workers=1
    ) as executor:

        first_future = executor.submit(
            first_worker
        )

        try:

            assert header_inserted.wait(
                timeout=10
            ), (
                "The first worker did not insert "
                "the report header."
            )

            with SessionLocal() as db:

                db.execute(
                    text(
                        """
                        SET LOCK_TIMEOUT 1000
                        """
                    )
                )

                try:

                    with pytest.raises(
                        DBAPIError
                    ):

                        ExecutionLeaseRepository(
                            db
                        ).acquire(
                            session_id=session_id,
                            duration_seconds=120,
                        )

                finally:

                    db.rollback()

        finally:

            allow_first_worker_to_finish.set()

        report_id = first_future.result(
            timeout=15
        )

    with SessionLocal() as db:

        persisted = ReportRepository(
            db
        ).get_for_session(
            session_id
        )

        report_count = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM dbo.research_reports
                WHERE research_session_id = :session_id
                """
            ),
            {
                "session_id": session_id,
            },
        ).scalar_one()

    assert persisted is not None

    assert persisted.id == report_id

    assert report_count == 1
