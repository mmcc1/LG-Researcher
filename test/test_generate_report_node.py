
from unittest.mock import Mock

from sqlalchemy import (
    delete,
    select,
)

from domain.report import (
    ReportSection,
)

from domain.report_synthesis import (
    ReportSynthesis,
)

from nodes.generate_report import (
    GenerateReportNode,
)

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import (
    ResearchReportEntity,
    ReportSectionEntity,
    ReportSectionClaim,
    ReportLimitation,
)

from persistence.report_repository import (
    ReportRepository,
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

from processing.report_context_builder import (
    ReportContextBuilder,
)

from processing.report_section_context_builder import (
    ReportSectionContextBuilder,
)

from processing.report_validator import (
    ReportValidator,
)

from test_report_plan_persistence import (
    build_test_plan,
    create_test_session,
    delete_test_session,
)


def build_test_section(
    plan,
    ordinal: int,
) -> ReportSection:

    planned_section = next(
        section
        for section in plan.sections
        if section.ordinal == ordinal
    )

    return ReportSection(
        heading=planned_section.heading,
        content=(
            f"This section presents the reviewed "
            f"evidence for {planned_section.heading}. "
            f"The available evidence is limited "
            f"to the supplied reviewed claims."
        ),
        reviewed_claim_ids=list(
            planned_section.reviewed_claim_ids
        ),
    )


def build_test_synthesis() -> ReportSynthesis:

    return ReportSynthesis(
        executive_summary=(
            "The research presents findings "
            "from the reviewed evidence."
        ),
        conclusions=(
            "The conclusions are limited "
            "to the reviewed findings."
        ),
        limitations=[
            "The available evidence is limited in scope.",
            "Further verification may be required.",
        ],
    )


def delete_final_report(
    db,
    session_id: str,
) -> None:

    report_ids = db.execute(
        select(
            ResearchReportEntity.id
        )
        .where(
            ResearchReportEntity.research_session_id
            == session_id
        )
    ).scalars().all()

    if not report_ids:

        return

    section_ids = db.execute(
        select(
            ReportSectionEntity.id
        )
        .where(
            ReportSectionEntity.research_report_id.in_(
                report_ids
            )
        )
    ).scalars().all()

    if section_ids:

        db.execute(
            delete(
                ReportSectionClaim
            )
            .where(
                ReportSectionClaim.report_section_id.in_(
                    section_ids
                )
            )
        )

    db.execute(
        delete(
            ReportSectionEntity
        )
        .where(
            ReportSectionEntity.research_report_id.in_(
                report_ids
            )
        )
    )

    db.execute(
        delete(
            ReportLimitation
        )
        .where(
            ReportLimitation.research_report_id.in_(
                report_ids
            )
        )
    )

    db.execute(
        delete(
            ResearchReportEntity
        )
        .where(
            ResearchReportEntity.id.in_(
                report_ids
            )
        )
    )

    db.commit()


def create_controlled_node(
    plan,
    synthesis,
):

    report_agent = Mock()

    report_agent.plan.return_value = (
        plan
    )

    section_agent = Mock()

    section_agent.generate.side_effect = (
        lambda topic,
        section,
        reviewed_evidence,
        preceding_context="": (
            build_test_section(
                plan=plan,
                ordinal=section.ordinal,
            )
        )
    )

    synthesis_agent = Mock()

    synthesis_agent.generate.return_value = (
        synthesis
    )

    node = GenerateReportNode(
        session_factory=SessionLocal,
        report_agent=report_agent,
        context_builder=ReportContextBuilder(),
        validator=ReportValidator(),
        report_section_agent=section_agent,
        report_synthesis_agent=synthesis_agent,
        section_context_builder=(
            ReportSectionContextBuilder()
        ),
        report_assembler=ReportAssembler(),
    )

    return (
        node,
        report_agent,
        section_agent,
        synthesis_agent,
    )


def persist_plan(
    session_id,
    plan,
    lease,
) -> None:

    with SessionLocal() as db:

        repository = ReportPlanRepository(
            db
        )

        repository.save_plan_fenced(
            session_id=session_id,
            plan=plan,
            lease=lease,
        )


def persist_section(
    session_id,
    plan,
    ordinal,
    lease,
) -> None:

    section = build_test_section(
        plan=plan,
        ordinal=ordinal,
    )

    with SessionLocal() as db:

        repository = (
            ReportGeneratedSectionRepository(
                db
            )
        )

        repository.save_section_fenced(
            session_id=session_id,
            ordinal=ordinal,
            section=section,
            lease=lease,
        )


def persist_synthesis(
    session_id,
    synthesis,
    lease,
) -> None:

    with SessionLocal() as db:

        repository = (
            ReportSynthesisRepository(
                db
            )
        )

        repository.save_synthesis_fenced(
            session_id=session_id,
            synthesis=synthesis,
            lease=lease,
        )


def get_final_report(
    session_id,
):

    with SessionLocal() as db:

        repository = ReportRepository(
            db
        )

        return repository.get_for_session(
            session_id
        )


def execute_node(
    node,
    session_id,
    lease,
    execution_guard,
):

    state = {
        "session_id": session_id,
        "topic": (
            "Report plan persistence integration test"
        ),
    }

    config = {
        "configurable": {
            "execution_lease": lease,
            "execution_guard": execution_guard,
        }
    }

    return node(
        state,
        config,
    )


def assert_report_complete(
    session_id,
    plan,
) -> None:

    report = get_final_report(
        session_id
    )

    if report is None:

        raise AssertionError(
            "Final research report was not persisted."
        )

    if report.title != plan.title:

        raise AssertionError(
            "Final report title does not match the plan."
        )

    if len(report.sections) != len(plan.sections):

        raise AssertionError(
            "Final report has an unexpected section count."
        )

    for planned, generated in zip(
        plan.sections,
        report.sections,
    ):

        if planned.heading != generated.heading:

            raise AssertionError(
                "Final report section heading mismatch."
            )

        if (
            set(planned.reviewed_claim_ids)
            != set(generated.reviewed_claim_ids)
        ):

            raise AssertionError(
                "Final report claim references mismatch."
            )


def run_scenario(
    scenario: str,
) -> None:

    session_id = None
    lease = None

    try:

        with SessionLocal() as db:

            session_id, claim_ids = (
                create_test_session(
                    db
                )
            )

        plan = build_test_plan(
            claim_ids
        )

        synthesis = build_test_synthesis()

        with SessionLocal() as db:

            lease_repository = (
                ExecutionLeaseRepository(
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

        if scenario in {
            "partial",
            "synthesis",
            "existing",
        }:

            persist_plan(
                session_id=session_id,
                plan=plan,
                lease=lease,
            )

        if scenario in {
            "partial",
            "synthesis",
            "existing",
        }:

            persist_section(
                session_id=session_id,
                plan=plan,
                ordinal=1,
                lease=lease,
            )

        if scenario in {
            "synthesis",
            "existing",
        }:

            persist_section(
                session_id=session_id,
                plan=plan,
                ordinal=2,
                lease=lease,
            )

        if scenario in {
            "synthesis",
            "existing",
        }:

            persist_synthesis(
                session_id=session_id,
                synthesis=synthesis,
                lease=lease,
            )

        if scenario == "existing":

            with SessionLocal() as db:

                generated_repository = (
                    ReportGeneratedSectionRepository(
                        db
                    )
                )

                generated_sections = (
                    generated_repository.get_generated_sections(
                        session_id
                    )
                )

            report = ReportAssembler().assemble(
                plan=plan,
                generated_sections=generated_sections,
                synthesis=synthesis,
                valid_reviewed_claim_ids=set(
                    claim_ids
                ),
            )

            with SessionLocal() as db:

                repository = ReportRepository(
                    db
                )

                repository.save_report_fenced(
                    session_id=session_id,
                    report=report,
                    lease=lease,
                )

        #
        # Simulate recovery using a new execution
        # lease after the original worker releases it.
        #

        if scenario != "fresh":

            with SessionLocal() as db:

                lease_repository = (
                    ExecutionLeaseRepository(
                        db
                    )
                )

                released = lease_repository.release(
                    lease
                )

                if not released:

                    raise AssertionError(
                        "Could not release the initial lease."
                    )

                lease = lease_repository.acquire(
                    session_id
                )

            if lease is None:

                raise AssertionError(
                    "Could not acquire recovery lease."
                )

        (
            node,
            report_agent,
            section_agent,
            synthesis_agent,
        ) = create_controlled_node(
            plan=plan,
            synthesis=synthesis,
        )

        guard = Mock()

        result = execute_node(
            node=node,
            session_id=session_id,
            lease=lease,
            execution_guard=guard,
        )

        if result != {}:

            raise AssertionError(
                "Unexpected graph node result."
            )

        assert_report_complete(
            session_id=session_id,
            plan=plan,
        )

        expected_calls = {
            "fresh": (1, 2, 1),
            "partial": (0, 1, 1),
            "synthesis": (0, 0, 0),
            "existing": (0, 0, 0),
        }

        expected = expected_calls[
            scenario
        ]

        actual = (
            report_agent.plan.call_count,
            section_agent.generate.call_count,
            synthesis_agent.generate.call_count,
        )

        if actual != expected:

            raise AssertionError(
                f"Unexpected agent calls for {scenario}. "
                f"Expected {expected}, got {actual}."
            )

        if guard.call_count == 0:

            raise AssertionError(
                "Execution guard was not invoked."
            )

        if scenario == "fresh":

            if guard.call_count < 8:

                raise AssertionError(
                    "Execution guard was not checked "
                    "at the expected model boundaries."
                )

        if scenario == "partial":

            generated_ordinal = (
                section_agent.generate.call_args
                .kwargs["section"].ordinal
            )

            if generated_ordinal != 2:

                raise AssertionError(
                    "Recovery regenerated the wrong section."
                )

        print(
            f"{scenario.capitalize()} report generation: PASSED"
        )

    finally:

        if session_id is not None:

            with SessionLocal() as db:

                db.rollback()

                delete_final_report(
                    db=db,
                    session_id=session_id,
                )

                delete_test_session(
                    db=db,
                    session_id=session_id,
                )


def test_released_lease() -> None:

    session_id = None

    try:

        with SessionLocal() as db:

            session_id, claim_ids = (
                create_test_session(
                    db
                )
            )

        plan = build_test_plan(
            claim_ids
        )

        synthesis = build_test_synthesis()

        with SessionLocal() as db:

            repository = (
                ExecutionLeaseRepository(
                    db
                )
            )

            lease = repository.acquire(
                session_id
            )

            if lease is None:

                raise AssertionError(
                    "Could not acquire execution lease."
                )

            released = repository.release(
                lease
            )

            if not released:

                raise AssertionError(
                    "Could not release execution lease."
                )

        (
            node,
            report_agent,
            section_agent,
            synthesis_agent,
        ) = create_controlled_node(
            plan=plan,
            synthesis=synthesis,
        )

        try:

            execute_node(
                node=node,
                session_id=session_id,
                lease=lease,
                execution_guard=Mock(),
            )

        except ExecutionLeaseFenceRejected:

            pass

        else:

            raise AssertionError(
                "Released execution lease was accepted."
            )

        if (
            report_agent.plan.call_count != 0
            or section_agent.generate.call_count != 0
            or synthesis_agent.generate.call_count != 0
        ):

            raise AssertionError(
                "Model invocation occurred after "
                "the execution lease was released."
            )

        if get_final_report(session_id) is not None:

            raise AssertionError(
                "A final report was persisted using "
                "a released execution lease."
            )

        print(
            "Released execution lease rejection: PASSED"
        )

    finally:

        if session_id is not None:

            with SessionLocal() as db:

                db.rollback()

                delete_final_report(
                    db=db,
                    session_id=session_id,
                )

                delete_test_session(
                    db=db,
                    session_id=session_id,
                )


def main():

    print()
    print(
        "GENERATE REPORT NODE INTEGRATION TEST"
    )

    print()

    run_scenario(
        "fresh"
    )

    run_scenario(
        "partial"
    )

    run_scenario(
        "synthesis"
    )

    run_scenario(
        "existing"
    )

    test_released_lease()

    print()
    print(
        "All generate report node tests: PASSED"
    )


if __name__ == "__main__":

    main()
