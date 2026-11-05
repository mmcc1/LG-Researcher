
from dataclasses import replace
from uuid import uuid4

from domain.report import (
    ResearchReport,
    ReportSection,
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

from test_search_result_fencing import (
    create_session,
    delete_session,
    expire_lease,
)

from test_review_completion_fencing import (
    acquire_lease,
)

from test_review_selection_fencing import (
    set_session_status,
)

from sqlalchemy import text




def delete_report(
    session_id: str,
) -> None:

    with SessionLocal() as db:

        try:

            #
            # Delete section provenance first.
            #

            db.execute(
                text(
                    """
                    DELETE rsc
                    FROM dbo.report_section_claims AS rsc
                    INNER JOIN dbo.report_sections AS rs
                        ON rs.id = rsc.report_section_id
                    INNER JOIN dbo.research_reports AS rr
                        ON rr.id = rs.research_report_id
                    WHERE rr.research_session_id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            #
            # Delete report limitations.
            #

            db.execute(
                text(
                    """
                    DELETE rl
                    FROM dbo.report_limitations AS rl
                    INNER JOIN dbo.research_reports AS rr
                        ON rr.id = rl.research_report_id
                    WHERE rr.research_session_id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            #
            # Delete report sections.
            #

            db.execute(
                text(
                    """
                    DELETE rs
                    FROM dbo.report_sections AS rs
                    INNER JOIN dbo.research_reports AS rr
                        ON rr.id = rs.research_report_id
                    WHERE rr.research_session_id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                },
            )

            #
            # Delete the report header.
            #

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

            db.commit()

        except Exception:

            db.rollback()

            raise


def make_report(
    claim_ids=None,
):

    claim_ids = (
        list(claim_ids)
        if claim_ids is not None
        else []
    )

    return ResearchReport(
        title="Deterministic Research Report",
        executive_summary=(
            "A reproducible report persistence test."
        ),
        sections=[
            ReportSection(
                heading="Evidence",
                content=(
                    "A section based on reviewed evidence."
                ),
                reviewed_claim_ids=(
                    claim_ids + claim_ids[:1]
                ),
            ),
            ReportSection(
                heading="Findings",
                content=(
                    "A second section based on the "
                    "same reviewed material."
                ),
                reviewed_claim_ids=claim_ids,
            ),
        ],
        conclusions=(
            "The reviewed evidence supports "
            "the stated findings."
        ),
        limitations=[
            "Limited source coverage.",
            "Further validation may be required.",
        ],
    )


def persist_report(
    session_id,
    report,
    lease,
):

    with SessionLocal() as db:

        return ReportRepository(
            db
        ).save_report_fenced(
            session_id=session_id,
            report=report,
            lease=lease,
        )


def load_report(
    session_id,
):

    with SessionLocal() as db:

        return ReportRepository(
            db
        ).get_for_session(
            session_id
        )


def expect_rejection(
    session_id,
    report,
    lease,
    expected_exception,
    protected_sessions,
):

    before = {
        item: load_report(item)
        for item in protected_sessions
    }

    try:

        persist_report(
            session_id,
            report,
            lease,
        )

    except expected_exception:

        pass

    else:

        raise AssertionError(
            "Report persistence was "
            "unexpectedly accepted."
        )

    after = {
        item: load_report(item)
        for item in protected_sessions
    }

    assert after == before, (
        "Rejected report persistence "
        "modified durable report state."
    )


def main():

    print()
    print("REPORT PERSISTENCE FENCING")
    print("==========================")

    sessions = []

    try:

        session_a = create_session()
        sessions.append(session_a)

        session_b = create_session()
        sessions.append(session_b)

        session_c = create_session()
        sessions.append(session_c)

        session_d = create_session()
        sessions.append(session_d)

        for session_id in sessions:

            set_session_status(
                session_id,
                "reporting",
            )

        lease_a = acquire_lease(
            session_a
        )

        lease_b = acquire_lease(
            session_b
        )

        lease_c = acquire_lease(
            session_c
        )

        lease_d = acquire_lease(
            session_d
        )

        #
        # Save a report with no claim references.
        #
        # Claim ownership is tested separately
        # using persisted review provenance.
        #

        report_a = make_report()

        report_id = persist_report(
            session_a,
            report_a,
            lease_a,
        )

        persisted = load_report(
            session_a
        )

        assert persisted is not None
        assert persisted.id == report_id

        print(
            "TEST 1 - Report persisted: PASSED"
        )

        #
        # Verify report hierarchy.
        #

        assert persisted.title == report_a.title

        assert (
            persisted.executive_summary
            == report_a.executive_summary
        )

        assert (
            persisted.conclusions
            == report_a.conclusions
        )

        assert len(persisted.sections) == 2

        assert [
            section.ordinal
            for section in persisted.sections
        ] == [1, 2]

        assert [
            section.heading
            for section in persisted.sections
        ] == [
            "Evidence",
            "Findings",
        ]

        assert persisted.limitations == [
            "Limited source coverage.",
            "Further validation may be required.",
        ]

        print(
            "TEST 2 - Complete report hierarchy: PASSED"
        )

        #
        # Idempotent recovery.
        #

        recovered_id = persist_report(
            session_a,
            None,
            lease_a,
        )

        assert recovered_id == report_id

        assert load_report(
            session_a
        ) == persisted

        print(
            "TEST 3 - Idempotent recovery: PASSED"
        )

        #
        # Incorrect owner.
        #

        invalid_lease = replace(
            lease_b,
            owner=str(uuid4()),
        )

        expect_rejection(
            session_b,
            make_report(),
            invalid_lease,
            ExecutionLeaseFenceRejected,
            [session_a, session_b],
        )

        print(
            "TEST 4 - Incorrect owner rejected: PASSED"
        )

        #
        # Expired lease.
        #

        expire_lease(
            session_b
        )

        expect_rejection(
            session_b,
            make_report(),
            lease_b,
            ExecutionLeaseFenceRejected,
            [session_b],
        )

        print(
            "TEST 5 - Expired lease rejected: PASSED"
        )

        #
        # Superseded lease.
        #

        replacement_lease_b = acquire_lease(
            session_b
        )

        assert (
            replacement_lease_b.version
            > lease_b.version
        )

        expect_rejection(
            session_b,
            make_report(),
            lease_b,
            ExecutionLeaseFenceRejected,
            [session_b],
        )

        print(
            "TEST 6 - Superseded lease rejected: PASSED"
        )

        #
        # Replacement worker succeeds.
        #

        report_b = make_report()

        replacement_report_id = persist_report(
            session_b,
            report_b,
            replacement_lease_b,
        )

        assert (
            load_report(session_b).id
            == replacement_report_id
        )

        print(
            "TEST 7 - Replacement lease succeeds: PASSED"
        )

        #
        # Cross-session lease.
        #

        expect_rejection(
            session_c,
            make_report(),
            lease_a,
            ValueError,
            [session_a, session_c],
        )

        print(
            "TEST 8 - Cross-session lease rejected: PASSED"
        )

        #
        # Invalid session lifecycle state.
        #

        set_session_status(
            session_c,
            "reviewed",
        )

        expect_rejection(
            session_c,
            make_report(),
            lease_c,
            ValueError,
            [session_c],
        )

        print(
            "TEST 9 - Invalid lifecycle state rejected: PASSED"
        )

        set_session_status(
            session_c,
            "reporting",
        )

        #
        # Foreign claim reference.
        #
        # Use an impossible reviewed-claim ID to
        # verify rejection before any insert.
        #

        invalid_report = make_report(
            [2147483647]
        )

        expect_rejection(
            session_c,
            invalid_report,
            lease_c,
            ValueError,
            [session_c],
        )

        assert load_report(
            session_c
        ) is None

        print(
            "TEST 10 - Invalid provenance rejected: PASSED"
        )

        #
        # Recovery after rejected provenance.
        #

        recovered_report_id = persist_report(
            session_c,
            make_report(),
            lease_c,
        )

        assert (
            load_report(session_c).id
            == recovered_report_id
        )

        print(
            "TEST 11 - Recovery after rejection: PASSED"
        )

        #
        # A report cannot be saved before
        # reporting has started.
        #

        set_session_status(
            session_d,
            "researched",
        )

        expect_rejection(
            session_d,
            make_report(),
            lease_d,
            ValueError,
            [session_d],
        )

        print(
            "TEST 12 - Premature persistence rejected: PASSED"
        )

        #
        # Session isolation.
        #

        assert load_report(
            session_a
        ).id == report_id

        assert load_report(
            session_b
        ).id == replacement_report_id

        assert load_report(
            session_c
        ).id == recovered_report_id

        assert load_report(
            session_d
        ) is None

        print(
            "TEST 13 - Session isolation preserved: PASSED"
        )

        print()
        print("PASS")

    finally:

        for session_id in reversed(
            sessions
        ):

            delete_report(
                session_id
            )

            delete_session(
                session_id
            )


if __name__ == "__main__":

    main()
