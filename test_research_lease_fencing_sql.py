
from dataclasses import replace

import pytest

from sqlalchemy import text

from domain.review import ResearchQuestionReview

from domain.report import (
    ResearchReport,
    ReportSection,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseFenceRejected,
)

from persistence.research_job_repository import (
    ResearchJobRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.review_repository import (
    ReviewRepository,
)

from persistence.report_repository import (
    ReportRepository,
)

from test_research_graph_recovery_sql import (
    test_environment,
    create_test_user,
    create_failed_recovery_job,
    cleanup_test_user_and_job,
)


def create_review():

    return ResearchQuestionReview(
        answer=(
            "Insufficient evidence to answer "
            "the research question."
        ),
        reviewed_claims=[],
        contradictions=[],
        evidence_gaps=[
            "No research findings were available.",
        ],
        overall_confidence="low",
        sufficient_evidence=False,
    )


def create_report(
    title,
):

    return ResearchReport(
        title=title,
        executive_summary=(
            "The available research evidence "
            "is insufficient."
        ),
        sections=[
            ReportSection(
                heading="Evidence Assessment",
                content=(
                    "No supporting research findings "
                    "were available."
                ),
                reviewed_claim_ids=[],
            ),
        ],
        conclusions=(
            "Further research is required."
        ),
        limitations=[
            "No supporting findings were available.",
        ],
    )


def acquire_session_lease(
    Session,
    session_id,
):

    with Session() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        return repository.acquire(
            session_id=session_id,
            duration_seconds=120,
        )


def release_session_lease(
    Session,
    lease,
):

    with Session() as db:

        repository = ExecutionLeaseRepository(
            db
        )

        return repository.release(
            lease
        )


def get_job_state(
    Session,
    job_id,
):

    with Session() as db:

        row = db.execute(
            text("""
                SELECT
                    status,
                    execution_owner,
                    lease_version,
                    last_error
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job_id,
            },
        ).one()

        return {
            "status": row[0],
            "owner": row[1],
            "version": row[2],
            "error": row[3],
        }


def get_review_count(
    Session,
    question_id,
):

    with Session() as db:

        return db.execute(
            text("""
                SELECT COUNT(*)
                FROM dbo.question_reviews
                WHERE research_question_id = :question_id
            """),
            {
                "question_id": question_id,
            },
        ).scalar_one()


def get_report_count(
    Session,
    session_id,
):

    with Session() as db:

        return db.execute(
            text("""
                SELECT COUNT(*)
                FROM dbo.research_reports
                WHERE research_session_id = :session_id
            """),
            {
                "session_id": session_id,
            },
        ).scalar_one()


def test_stale_job_lease_cannot_modify_reclaimed_job(
    test_environment,
):

    Session, session_ids = test_environment

    user_id = create_test_user(
        Session
    )

    try:

        (
            job_id,
            session_id,
            _,
            _,
        ) = create_failed_recovery_job(
            Session,
            user_id,
            session_ids,
        )

        #
        # Claim the queued job.
        #

        with Session() as db:

            repository = ResearchJobRepository(
                db
            )

            first_claim = repository.claim_next(
                duration_seconds=120
            )

            assert first_claim is not None

            assert first_claim.job_id == job_id

            old_lease = first_claim.lease

        #
        # Simulate expiry using SQL Server time.
        #
        # Only the synthetic test job is modified.
        #

        with Session() as db:

            result = db.execute(
                text("""
                    UPDATE dbo.research_jobs
                    SET lease_expires_at = DATEADD(
                        second,
                        -1,
                        SYSUTCDATETIME()
                    )
                    WHERE id = :job_id
                      AND execution_owner = :owner
                      AND lease_version = :version
                      AND status = 'claimed'
                """),
                {
                    "job_id": job_id,
                    "owner": old_lease.owner,
                    "version": old_lease.version,
                },
            )

            assert result.rowcount == 1

            db.commit()

        #
        # Another worker reclaims the expired job.
        #

        with Session() as db:

            repository = ResearchJobRepository(
                db
            )

            second_claim = repository.claim_next(
                duration_seconds=120
            )

            assert second_claim is not None

            assert second_claim.job_id == job_id

            new_lease = second_claim.lease

        assert new_lease.owner != old_lease.owner

        assert new_lease.version > old_lease.version

        #
        # The previous worker must not renew,
        # fail, or complete the reclaimed job.
        #

        with Session() as db:

            repository = ResearchJobRepository(
                db
            )

            assert repository.renew(
                old_lease
            ) is None

            assert repository.fail(
                lease=old_lease,
                error="Stale worker attempted failure.",
            ) is False

            assert repository.complete(
                old_lease
            ) is False

        current_state = get_job_state(
            Session,
            job_id,
        )

        assert current_state["status"] == "claimed"

        assert current_state["owner"] == new_lease.owner

        assert current_state["version"] == new_lease.version

        #
        # The current owner must still be able
        # to perform an authorised transition.
        #

        with Session() as db:

            repository = ResearchJobRepository(
                db
            )

            assert repository.fail(
                lease=new_lease,
                error="Controlled test termination.",
            ) is True

        final_state = get_job_state(
            Session,
            job_id,
        )

        assert final_state["status"] == "failed"

        assert final_state["owner"] is None

    finally:

        cleanup_test_user_and_job(
            Session,
            user_id,
        )


def test_stale_session_lease_cannot_persist_review(
    test_environment,
):

    Session, session_ids = test_environment

    user_id = create_test_user(
        Session
    )

    try:

        (
            job_id,
            session_id,
            first_question_id,
            second_question_id,
        ) = create_failed_recovery_job(
            Session,
            user_id,
            session_ids,
        )

        old_lease = acquire_session_lease(
            Session,
            session_id,
        )

        #
        # The first execution ends.
        # A replacement acquires a new version.
        #

        assert release_session_lease(
            Session,
            old_lease,
        ) is True

        new_lease = acquire_session_lease(
            Session,
            session_id,
        )

        try:

            assert new_lease.owner != old_lease.owner

            assert new_lease.version > old_lease.version

            #
            # Verify the stale lease is rejected.
            #

            with Session() as db:

                repository = ExecutionLeaseRepository(
                    db
                )

                with pytest.raises(
                    ExecutionLeaseFenceRejected
                ):

                    repository.fence(
                        old_lease
                    )

            #
            # The stale worker attempts to persist
            # a review for an existing question.
            #

            with Session() as db:

                repository = ReviewRepository(
                    db
                )

                with pytest.raises(
                    ExecutionLeaseFenceRejected
                ):

                    repository.save_review_fenced(
                        session_id=session_id,
                        question_id=first_question_id,
                        review=create_review(),
                        valid_finding_ids=set(),
                        lease=old_lease,
                    )

            assert get_review_count(
                Session,
                first_question_id,
            ) == 0

            #
            # The replacement worker can persist
            # the review successfully.
            #

            with Session() as db:

                repository = ReviewRepository(
                    db
                )

                review_id = repository.save_review_fenced(
                    session_id=session_id,
                    question_id=first_question_id,
                    review=create_review(),
                    valid_finding_ids=set(),
                    lease=new_lease,
                )

                assert review_id is not None

            assert get_review_count(
                Session,
                first_question_id,
            ) == 1

            #
            # The old worker cannot release the
            # replacement worker's lease.
            #

            assert release_session_lease(
                Session,
                old_lease,
            ) is False

            with Session() as db:

                repository = ExecutionLeaseRepository(
                    db
                )

                repository.fence(
                    new_lease
                )

                db.rollback()

        finally:

            release_session_lease(
                Session,
                new_lease,
            )

    finally:

        cleanup_test_user_and_job(
            Session,
            user_id,
        )


def test_stale_session_lease_cannot_persist_report(
    test_environment,
):

    Session, session_ids = test_environment

    user_id = create_test_user(
        Session
    )

    try:

        (
            job_id,
            session_id,
            first_question_id,
            second_question_id,
        ) = create_failed_recovery_job(
            Session,
            user_id,
            session_ids,
        )

        #
        # Prepare a synthetic session that has
        # reached the reporting phase.
        #
        # This test isolates report fencing,
        # not review lifecycle transitions.
        #

        with Session() as db:

            repository = ResearchSessionRepository(
                db
            )

            repository.set_status(
                session_id=session_id,
                status="reporting",
            )

        old_lease = acquire_session_lease(
            Session,
            session_id,
        )

        assert release_session_lease(
            Session,
            old_lease,
        ) is True

        new_lease = acquire_session_lease(
            Session,
            session_id,
        )

        try:

            assert new_lease.version > old_lease.version

            #
            # A stale execution cannot insert
            # a report after ownership changes.
            #

            with Session() as db:

                repository = ReportRepository(
                    db
                )

                with pytest.raises(
                    ExecutionLeaseFenceRejected
                ):

                    repository.save_report_fenced(
                        session_id=session_id,
                        report=create_report(
                            "Stale Worker Report"
                        ),
                        lease=old_lease,
                    )

            assert get_report_count(
                Session,
                session_id,
            ) == 0

            #
            # The replacement execution persists
            # its report using the valid lease.
            #

            with Session() as db:

                repository = ReportRepository(
                    db
                )

                original_report_id = (
                    repository.save_report_fenced(
                        session_id=session_id,
                        report=create_report(
                            "Current Owner Report"
                        ),
                        lease=new_lease,
                    )
                )

                assert original_report_id is not None

            assert get_report_count(
                Session,
                session_id,
            ) == 1

            #
            # The old worker attempts to replace
            # the already-persisted report.
            #

            with Session() as db:

                repository = ReportRepository(
                    db
                )

                with pytest.raises(
                    ExecutionLeaseFenceRejected
                ):

                    repository.save_report_fenced(
                        session_id=session_id,
                        report=create_report(
                            "Stale Overwrite Attempt"
                        ),
                        lease=old_lease,
                    )

            #
            # Verify the original persisted report
            # remains unchanged.
            #

            with Session() as db:

                repository = ReportRepository(
                    db
                )

                persisted_report = repository.get_for_session(
                    session_id
                )

                assert persisted_report is not None

                assert persisted_report.id == original_report_id

                assert persisted_report.title == (
                    "Current Owner Report"
                )

            assert get_report_count(
                Session,
                session_id,
            ) == 1

            #
            # The replacement lease remains valid.
            #

            with Session() as db:

                repository = ExecutionLeaseRepository(
                    db
                )

                repository.fence(
                    new_lease
                )

                db.rollback()

        finally:

            release_session_lease(
                Session,
                new_lease,
            )

    finally:

        cleanup_test_user_and_job(
            Session,
            user_id,
        )
