
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

from processing.report_assembler import (
    ReportAssembler,
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

            print()
            print(
                "REPORT ASSEMBLY PERSISTENCE TEST"
            )

            print()
            print(
                f"Test session: {session_id}"
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

            assembler = ReportAssembler()

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

            print(
                "Report plan persistence: PASSED"
            )

            first_section = ReportSection(
                heading="First Test Section",
                content=(
                    "The first reviewed claim provides "
                    "evidence relevant to the research "
                    "question. This section presents "
                    "that evidence."
                ),
                reviewed_claim_ids=[
                    claim_ids[0],
                ],
            )

            second_section = ReportSection(
                heading="Second Test Section",
                content=(
                    "The remaining reviewed claims "
                    "provide additional findings. "
                    "This section examines their "
                    "implications for the research."
                ),
                reviewed_claim_ids=[
                    claim_ids[1],
                    claim_ids[2],
                ],
            )

            section_repository.save_section_fenced(
                session_id=session_id,
                ordinal=1,
                section=first_section,
                lease=lease,
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
                    "Generated report sections "
                    "are incomplete."
                )

            print(
                "Generated section persistence: PASSED"
            )

            synthesis = ReportSynthesis(
                executive_summary=(
                    "The research presents reviewed "
                    "findings supported by the "
                    "available evidence."
                ),
                conclusions=(
                    "The reviewed findings support "
                    "the conclusions presented "
                    "in this report."
                ),
                limitations=[
                    (
                        "The available evidence "
                        "is limited in scope."
                    ),
                    (
                        "Further verification "
                        "may be required."
                    ),
                ],
            )

            synthesis_repository.save_synthesis_fenced(
                session_id=session_id,
                synthesis=synthesis,
                lease=lease,
            )

            print(
                "Report synthesis persistence: PASSED"
            )

            released = lease_repository.release(
                lease
            )

            if not released:

                raise AssertionError(
                    "Could not release the "
                    "initial execution lease."
                )

            print(
                "Initial execution lease released: PASSED"
            )

            recovery_lease = (
                lease_repository.acquire(
                    session_id
                )
            )

            if recovery_lease is None:

                raise AssertionError(
                    "Could not acquire recovery lease."
                )

            if recovery_lease.version <= lease.version:

                raise AssertionError(
                    "Recovery lease fencing version "
                    "did not advance."
                )

            print(
                "Recovery execution lease acquired: PASSED"
            )

            persisted_plan = (
                plan_repository.get_for_session(
                    session_id
                )
            )

            if persisted_plan is None:

                raise AssertionError(
                    "Persisted report plan "
                    "could not be reloaded."
                )

            if persisted_plan != plan:

                raise AssertionError(
                    "Reloaded report plan "
                    "differs from the original."
                )

            print(
                "Report plan recovery: PASSED"
            )

            persisted_sections = (
                section_repository.get_generated_sections(
                    session_id
                )
            )

            if len(persisted_sections) != 2:

                raise AssertionError(
                    "Expected two persisted "
                    "generated sections."
                )

            if persisted_sections[0].ordinal != 1:

                raise AssertionError(
                    "First persisted section "
                    "has an unexpected ordinal."
                )

            if persisted_sections[1].ordinal != 2:

                raise AssertionError(
                    "Second persisted section "
                    "has an unexpected ordinal."
                )

            if (
                persisted_sections[0].content
                != first_section.content
            ):

                raise AssertionError(
                    "First persisted section "
                    "content mismatch."
                )

            if (
                persisted_sections[1].content
                != second_section.content
            ):

                raise AssertionError(
                    "Second persisted section "
                    "content mismatch."
                )

            if (
                set(persisted_sections[0].reviewed_claim_ids)
                != set(first_section.reviewed_claim_ids)
            ):

                raise AssertionError(
                    "First persisted section "
                    "claim references mismatch."
                )

            if (
                set(persisted_sections[1].reviewed_claim_ids)
                != set(second_section.reviewed_claim_ids)
            ):

                raise AssertionError(
                    "Second persisted section "
                    "claim references mismatch."
                )

            print(
                "Generated section recovery: PASSED"
            )

            persisted_synthesis = (
                synthesis_repository.get_for_session(
                    session_id
                )
            )

            if persisted_synthesis is None:

                raise AssertionError(
                    "Persisted synthesis "
                    "could not be reloaded."
                )

            if persisted_synthesis != synthesis:

                raise AssertionError(
                    "Reloaded synthesis differs "
                    "from the original."
                )

            print(
                "Report synthesis recovery: PASSED"
            )

            valid_reviewed_claim_ids = set(
                claim_ids
            )

            report = assembler.assemble(
                plan=persisted_plan,
                generated_sections=(
                    persisted_sections
                ),
                synthesis=persisted_synthesis,
                valid_reviewed_claim_ids=(
                    valid_reviewed_claim_ids
                ),
            )

            if report.title != plan.title:

                raise AssertionError(
                    "Assembled report title mismatch."
                )

            if len(report.sections) != 2:

                raise AssertionError(
                    "Assembled report does not "
                    "contain two sections."
                )

            if report.sections[0].heading != plan.sections[0].heading:

                raise AssertionError(
                    "First assembled section "
                    "heading mismatch."
                )

            if report.sections[1].heading != plan.sections[1].heading:

                raise AssertionError(
                    "Second assembled section "
                    "heading mismatch."
                )

            if report.sections[0].content != first_section.content:

                raise AssertionError(
                    "First assembled section "
                    "content mismatch."
                )

            if report.sections[1].content != second_section.content:

                raise AssertionError(
                    "Second assembled section "
                    "content mismatch."
                )

            if report.executive_summary != synthesis.executive_summary:

                raise AssertionError(
                    "Assembled executive summary mismatch."
                )

            if report.conclusions != synthesis.conclusions:

                raise AssertionError(
                    "Assembled conclusions mismatch."
                )

            if report.limitations != synthesis.limitations:

                raise AssertionError(
                    "Assembled limitations mismatch."
                )

            print(
                "Final report assembly: PASSED"
            )

            print()
            print(
                "ASSEMBLED REPORT"
            )

            print()
            print(
                f"Title: {report.title}"
            )

            print()
            print(
                f"Executive summary: {report.executive_summary}"
            )

            for index, section in enumerate(
                report.sections,
                start=1,
            ):

                print()
                print(
                    f"Section {index}: {section.heading}"
                )

                print(
                    section.content
                )

                print(
                    "Reviewed claim IDs: "
                    f"{section.reviewed_claim_ids}"
                )

            print()
            print(
                f"Conclusions: {report.conclusions}"
            )

            print()
            print(
                "Limitations:"
            )

            for limitation in report.limitations:

                print(
                    f"- {limitation}"
                )

            released = lease_repository.release(
                recovery_lease
            )

            if not released:

                raise AssertionError(
                    "Could not release "
                    "the recovery lease."
                )

            print()
            print(
                "Recovery execution lease released: PASSED"
            )

            print()
            print(
                "All report assembly persistence tests: PASSED"
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
