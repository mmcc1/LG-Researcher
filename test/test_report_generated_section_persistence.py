
from copy import deepcopy

from persistence.database import SessionLocal

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

from domain.report import ReportSection

from test_report_plan_persistence import (
    create_test_session,
    build_test_plan,
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

            print()
            print(
                "REPORT GENERATED SECTION PERSISTENCE TEST"
            )

            pending = section_repository.get_next_pending_section(
                session_id
            )

            if pending is None or pending.ordinal != 1:

                raise AssertionError(
                    "Expected first section to be pending."
                )

            print(
                "Initial pending section: PASSED"
            )

            first_section = ReportSection(
                heading="First Test Section",
                content=(
                    "This is a generated test section "
                    "based on the first reviewed claim."
                ),
                reviewed_claim_ids=[
                    claim_ids[0],
                ],
            )

            first_id = section_repository.save_section_fenced(
                session_id=session_id,
                ordinal=1,
                section=first_section,
                lease=lease,
            )

            generated_sections = (
                section_repository.get_generated_sections(
                    session_id
                )
            )

            if len(generated_sections) != 1:

                raise AssertionError(
                    "Expected one persisted generated section."
                )

            if generated_sections[0].id != first_id:

                raise AssertionError(
                    "Persisted section identity mismatch."
                )

            print(
                "Initial section persistence: PASSED"
            )

            retry_id = section_repository.save_section_fenced(
                session_id=session_id,
                ordinal=1,
                section=first_section,
                lease=lease,
            )

            if retry_id != first_id:

                raise AssertionError(
                    "Identical retry created a different section."
                )

            print(
                "Identical section retry: PASSED"
            )

            changed_section = deepcopy(
                first_section
            )

            changed_section.content = (
                "This is different generated content."
            )

            try:

                section_repository.save_section_fenced(
                    session_id=session_id,
                    ordinal=1,
                    section=changed_section,
                    lease=lease,
                )

            except ValueError:

                print(
                    "Modified section rejection: PASSED"
                )

            else:

                raise AssertionError(
                    "Modified generated section was accepted."
                )

            invalid_claim_section = ReportSection(
                heading="First Test Section",
                content="This section references an unallocated claim.",
                reviewed_claim_ids=[
                    claim_ids[1],
                ],
            )

            try:

                section_repository.save_section_fenced(
                    session_id=session_id,
                    ordinal=1,
                    section=invalid_claim_section,
                    lease=lease,
                )

            except ValueError:

                print(
                    "Unallocated claim rejection: PASSED"
                )

            else:

                raise AssertionError(
                    "Unallocated reviewed claim was accepted."
                )

            pending = section_repository.get_next_pending_section(
                session_id
            )

            if pending is None or pending.ordinal != 2:

                raise AssertionError(
                    "Expected second section to be pending."
                )

            print(
                "Recovery selects next section: PASSED"
            )

            released = lease_repository.release(
                lease
            )

            if not released:

                raise AssertionError(
                    "Could not release execution lease."
                )

            try:

                section_repository.save_section_fenced(
                    session_id=session_id,
                    ordinal=2,
                    section=ReportSection(
                        heading="Second Test Section",
                        content="Second section test content.",
                        reviewed_claim_ids=[
                            claim_ids[1],
                        ],
                    ),
                    lease=lease,
                )

            except ExecutionLeaseFenceRejected:

                print(
                    "Released lease fencing: PASSED"
                )

            else:

                raise AssertionError(
                    "Released lease was incorrectly accepted."
                )

            new_lease = lease_repository.acquire(
                session_id
            )

            if new_lease is None:

                raise AssertionError(
                    "Could not reacquire execution lease."
                )

            pending = section_repository.get_next_pending_section(
                session_id
            )

            if pending is None or pending.ordinal != 2:

                raise AssertionError(
                    "Recovery did not retain saved progress."
                )

            print(
                "Progress survives lease change: PASSED"
            )

            second_section = ReportSection(
                heading="Second Test Section",
                content=(
                    "This is the second generated test section "
                    "based on the remaining reviewed claims."
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
                lease=new_lease,
            )

            pending = section_repository.get_next_pending_section(
                session_id
            )

            if pending is not None:

                raise AssertionError(
                    "A section remains pending after completion."
                )

            generated_sections = (
                section_repository.get_generated_sections(
                    session_id
                )
            )

            if len(generated_sections) != 2:

                raise AssertionError(
                    "Expected two generated sections."
                )

            print(
                "All planned sections persisted: PASSED"
            )

            lease_repository.release(
                new_lease
            )

            print()
            print(
                "All generated section persistence tests: PASSED"
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
