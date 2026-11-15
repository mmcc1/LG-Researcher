
from copy import deepcopy

from domain.report import (
    ReportSection,
)

from domain.report_synthesis import (
    ReportSynthesis,
)

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.report_plan_repository import (
    ReportPlanRepository,
)

from persistence.report_generated_section_repository import (
    ReportGeneratedSectionRepository,
)

from persistence.report_synthesis_repository import (
    ReportSynthesisRepository,
)

from test_report_plan_persistence import (
    build_test_plan,
    create_test_session,
    delete_test_session,
)


def main():

    session_id = None

    with SessionLocal() as db:

        try:

            session_id, claim_ids = (
                create_test_session(
                    db
                )
            )

            lease_repository = (
                ExecutionLeaseRepository(
                    db
                )
            )

            plan_repository = (
                ReportPlanRepository(
                    db
                )
            )

            section_repository = (
                ReportGeneratedSectionRepository(
                    db
                )
            )

            synthesis_repository = (
                ReportSynthesisRepository(
                    db
                )
            )

            lease = lease_repository.acquire(
                session_id
            )

            if lease is None:

                raise AssertionError(
                    "Could not acquire execution lease."
                )

            plan = build_test_plan(
                claim_ids
            )

            plan_repository.save_plan_fenced(
                session_id=session_id,
                plan=plan,
                lease=lease,
            )

            synthesis = ReportSynthesis(
                executive_summary=(
                    "The reviewed research identifies "
                    "several findings supported by "
                    "the available evidence."
                ),
                conclusions=(
                    "The evidence supports the "
                    "conclusions presented in "
                    "the completed report sections."
                ),
                limitations=[
                    (
                        "Some supporting evidence "
                        "remains incomplete."
                    ),
                    (
                        "Certain findings require "
                        "additional verification."
                    ),
                ],
            )

            print()
            print(
                "REPORT SYNTHESIS PERSISTENCE TEST"
            )

            print()
            print(
                f"Test session: {session_id}"
            )

            if synthesis_repository.exists_for_session(
                session_id
            ):

                raise AssertionError(
                    "Synthesis unexpectedly exists "
                    "before persistence."
                )

            if synthesis_repository.get_for_session(
                session_id
            ) is not None:

                raise AssertionError(
                    "Synthesis was returned before "
                    "it was persisted."
                )

            print(
                "Initial synthesis absence: PASSED"
            )

            try:

                synthesis_repository.save_synthesis_fenced(
                    session_id=session_id,
                    synthesis=synthesis,
                    lease=lease,
                )

            except ValueError:

                print(
                    "No generated sections rejection: PASSED"
                )

            else:

                raise AssertionError(
                    "Synthesis was accepted without "
                    "generated report sections."
                )

            first_section = ReportSection(
                heading="First Test Section",
                content=(
                    "This section presents findings "
                    "supported by the first reviewed "
                    "test claim."
                ),
                reviewed_claim_ids=[
                    claim_ids[0],
                ],
            )

            section_repository.save_section_fenced(
                session_id=session_id,
                ordinal=1,
                section=first_section,
                lease=lease,
            )

            try:

                synthesis_repository.save_synthesis_fenced(
                    session_id=session_id,
                    synthesis=synthesis,
                    lease=lease,
                )

            except ValueError:

                print(
                    "Incomplete sections rejection: PASSED"
                )

            else:

                raise AssertionError(
                    "Synthesis was accepted with "
                    "a planned section unfinished."
                )

            second_section = ReportSection(
                heading="Second Test Section",
                content=(
                    "This section presents the "
                    "remaining reviewed findings "
                    "and their implications."
                ),
                reviewed_claim_ids=[
                    claim_ids[1],
                    claim_ids[2],
                ],
            )

            section_repository.save_section_fenced(
                session_id=session_id,
                ordinal=2,
                section=second_section,
                lease=lease,
            )

            pending_section = (
                section_repository.get_next_pending_section(
                    session_id
                )
            )

            if pending_section is not None:

                raise AssertionError(
                    "Planned sections are not complete."
                )

            print(
                "All generated sections complete: PASSED"
            )

            synthesis_id = (
                synthesis_repository.save_synthesis_fenced(
                    session_id=session_id,
                    synthesis=synthesis,
                    lease=lease,
                )
            )

            if synthesis_id is None:

                raise AssertionError(
                    "Synthesis persistence returned no ID."
                )

            print(
                "Initial synthesis persistence: PASSED"
            )

            if not synthesis_repository.exists_for_session(
                session_id
            ):

                raise AssertionError(
                    "Persisted synthesis was not found."
                )

            persisted_synthesis = (
                synthesis_repository.get_for_session(
                    session_id
                )
            )

            if persisted_synthesis is None:

                raise AssertionError(
                    "Persisted synthesis could not "
                    "be reconstructed."
                )

            if persisted_synthesis != synthesis:

                raise AssertionError(
                    "Persisted synthesis differs "
                    "from the original synthesis."
                )

            print(
                "Synthesis reload and comparison: PASSED"
            )

            retry_id = (
                synthesis_repository.save_synthesis_fenced(
                    session_id=session_id,
                    synthesis=synthesis,
                    lease=lease,
                )
            )

            if retry_id != synthesis_id:

                raise AssertionError(
                    "Identical retry returned "
                    "a different synthesis ID."
                )

            print(
                "Identical synthesis retry: PASSED"
            )

            changed_synthesis = deepcopy(
                synthesis
            )

            changed_synthesis.conclusions = (
                "These conclusions differ "
                "from the persisted synthesis."
            )

            try:

                synthesis_repository.save_synthesis_fenced(
                    session_id=session_id,
                    synthesis=changed_synthesis,
                    lease=lease,
                )

            except ValueError:

                print(
                    "Modified synthesis rejection: PASSED"
                )

            else:

                raise AssertionError(
                    "Modified synthesis was accepted."
                )

            invalid_synthesis = ReportSynthesis(
                executive_summary="",
                conclusions="Valid conclusions.",
                limitations=[],
            )

            try:

                synthesis_repository.save_synthesis_fenced(
                    session_id=session_id,
                    synthesis=invalid_synthesis,
                    lease=lease,
                )

            except ValueError:

                print(
                    "Empty executive summary rejection: PASSED"
                )

            else:

                raise AssertionError(
                    "Empty executive summary was accepted."
                )

            invalid_synthesis = ReportSynthesis(
                executive_summary="Valid summary.",
                conclusions="",
                limitations=[],
            )

            try:

                synthesis_repository.save_synthesis_fenced(
                    session_id=session_id,
                    synthesis=invalid_synthesis,
                    lease=lease,
                )

            except ValueError:

                print(
                    "Empty conclusions rejection: PASSED"
                )

            else:

                raise AssertionError(
                    "Empty conclusions were accepted."
                )

            invalid_synthesis = ReportSynthesis(
                executive_summary="Valid summary.",
                conclusions="Valid conclusions.",
                limitations=[
                    "",
                ],
            )

            try:

                synthesis_repository.save_synthesis_fenced(
                    session_id=session_id,
                    synthesis=invalid_synthesis,
                    lease=lease,
                )

            except ValueError:

                print(
                    "Empty limitation rejection: PASSED"
                )

            else:

                raise AssertionError(
                    "Empty limitation was accepted."
                )

            released = lease_repository.release(
                lease
            )

            if not released:

                raise AssertionError(
                    "Execution lease could not be released."
                )

            print(
                "Execution lease release: PASSED"
            )

            try:

                synthesis_repository.save_synthesis_fenced(
                    session_id=session_id,
                    synthesis=synthesis,
                    lease=lease,
                )

            except ExecutionLeaseFenceRejected:

                print(
                    "Released lease fencing: PASSED"
                )

            else:

                raise AssertionError(
                    "Released execution lease "
                    "was incorrectly accepted."
                )

            new_lease = lease_repository.acquire(
                session_id
            )

            if new_lease is None:

                raise AssertionError(
                    "Could not reacquire execution lease."
                )

            if new_lease.version <= lease.version:

                raise AssertionError(
                    "New execution lease did not "
                    "advance the fencing version."
                )

            recovered_synthesis = (
                synthesis_repository.get_for_session(
                    session_id
                )
            )

            if recovered_synthesis != synthesis:

                raise AssertionError(
                    "Persisted synthesis was not "
                    "available after lease change."
                )

            print(
                "Synthesis survives lease change: PASSED"
            )

            recovered_id = (
                synthesis_repository.save_synthesis_fenced(
                    session_id=session_id,
                    synthesis=recovered_synthesis,
                    lease=new_lease,
                )
            )

            if recovered_id != synthesis_id:

                raise AssertionError(
                    "Recovery retry returned "
                    "a different synthesis ID."
                )

            print(
                "Recovery idempotency: PASSED"
            )

            released = lease_repository.release(
                new_lease
            )

            if not released:

                raise AssertionError(
                    "New execution lease could not "
                    "be released."
                )

            print()
            print(
                "All report synthesis persistence tests: PASSED"
            )

        finally:

            db.rollback()

            if session_id is not None:

                delete_test_session(
                    db=db,
                    session_id=session_id,
                )

                print(
                    "Test session cleanup: COMPLETED"
                )


if __name__ == "__main__":

    main()
