
from copy import deepcopy
from dataclasses import replace

from domain.report_plan import (
    PlannedReportSection,
    ReportPlan,
)

from domain.report_synthesis import (
    ReportSynthesis,
)

from persistence.report_generated_section_repository import (
    PersistedGeneratedSection,
)

from processing.report_assembler import (
    ReportAssembler,
)



def expect_rejection(
    action,
    description: str,
) -> None:

    try:

        action()

    except ValueError:

        print(
            f"{description}: PASSED"
        )

    else:

        raise AssertionError(
            f"{description}: expected ValueError."
        )


def main():

    plan = ReportPlan(
        title="Test Research Report",
        target_word_count=1000,
        executive_summary_word_count=50,
        conclusions_word_count=50,
        limitations_word_count=30,
        sections=[
            PlannedReportSection(
                ordinal=1,
                heading="First Test Section",
                purpose="Examine the first finding.",
                target_word_count=435,
                reviewed_claim_ids=[
                    101,
                ],
            ),
            PlannedReportSection(
                ordinal=2,
                heading="Second Test Section",
                purpose="Examine the remaining findings.",
                target_word_count=435,
                reviewed_claim_ids=[
                    102,
                    103,
                ],
            ),
        ],
    )

    first_section = PersistedGeneratedSection(
        id=1,
        ordinal=1,
        heading="First Test Section",
        content=(
            "The first reviewed finding provides "
            "evidence relevant to this research."
        ),
        actual_word_count=11,
        reviewed_claim_ids=[
            101,
        ],
    )

    second_section = PersistedGeneratedSection(
        id=2,
        ordinal=2,
        heading="Second Test Section",
        content=(
            "The remaining reviewed findings "
            "provide additional research evidence."
        ),
        actual_word_count=9,
        reviewed_claim_ids=[
            102,
            103,
        ],
    )

    synthesis = ReportSynthesis(
        executive_summary=(
            "The reviewed research provides "
            "several evidence-based findings."
        ),
        conclusions=(
            "The available evidence supports "
            "the reported conclusions."
        ),
        limitations=[
            "Some evidence remains incomplete.",
            "Further verification is required.",
        ],
    )

    valid_claim_ids = {
        101,
        102,
        103,
    }

    assembler = ReportAssembler()

    print()
    print(
        "REPORT ASSEMBLY TEST"
    )
    print()

    report = assembler.assemble(
        plan=plan,
        generated_sections=[
            second_section,
            first_section,
        ],
        synthesis=synthesis,
        valid_reviewed_claim_ids=(
            valid_claim_ids
        ),
    )

    if report.title != plan.title:

        raise AssertionError(
            "Assembled report title mismatch."
        )

    if len(report.sections) != 2:

        raise AssertionError(
            "Expected two assembled sections."
        )

    if report.sections[0].heading != "First Test Section":

        raise AssertionError(
            "First section is not in planned order."
        )

    if report.sections[1].heading != "Second Test Section":

        raise AssertionError(
            "Second section is not in planned order."
        )

    if report.executive_summary != synthesis.executive_summary:

        raise AssertionError(
            "Executive summary mismatch."
        )

    if report.conclusions != synthesis.conclusions:

        raise AssertionError(
            "Conclusions mismatch."
        )

    if report.limitations != synthesis.limitations:

        raise AssertionError(
            "Limitations mismatch."
        )

    print(
        "Successful report assembly: PASSED"
    )

    print(
        "Section ordering: PASSED"
    )

    print(
        "Synthesis reconstruction: PASSED"
    )

    expect_rejection(
        action=lambda: assembler.assemble(
            plan=plan,
            generated_sections=[
                first_section,
            ],
            synthesis=synthesis,
            valid_reviewed_claim_ids=(
                valid_claim_ids
            ),
        ),
        description="Incomplete sections rejection",
    )

    expect_rejection(
        action=lambda: assembler.assemble(
            plan=plan,
            generated_sections=[
                first_section,
                first_section,
            ],
            synthesis=synthesis,
            valid_reviewed_claim_ids=(
                valid_claim_ids
            ),
        ),
        description="Duplicate section rejection",
    )

    mismatched_section = replace(
        second_section,
        heading="Unexpected Section Heading",
    )

    expect_rejection(
        action=lambda: assembler.assemble(
            plan=plan,
            generated_sections=[
                first_section,
                mismatched_section,
            ],
            synthesis=synthesis,
            valid_reviewed_claim_ids=(
                valid_claim_ids
            ),
        ),
        description="Mismatched heading rejection",
    )

    invalid_claim_section = replace(
        second_section,
        reviewed_claim_ids=[
            101,
        ],
    )

    expect_rejection(
        action=lambda: assembler.assemble(
            plan=plan,
            generated_sections=[
                first_section,
                invalid_claim_section,
            ],
            synthesis=synthesis,
            valid_reviewed_claim_ids=(
                valid_claim_ids
            ),
        ),
        description="Unallocated claim rejection",
    )

    unknown_claim_section = replace(
        second_section,
        reviewed_claim_ids=[
            999,
        ],
    )

    expect_rejection(
        action=lambda: assembler.assemble(
            plan=plan,
            generated_sections=[
                first_section,
                unknown_claim_section,
            ],
            synthesis=synthesis,
            valid_reviewed_claim_ids=(
                valid_claim_ids
            ),
        ),
        description="Unknown claim rejection",
    )

    duplicate_claim_section = replace(
        second_section,
        reviewed_claim_ids=[
            102,
            102,
        ],
    )

    expect_rejection(
        action=lambda: assembler.assemble(
            plan=plan,
            generated_sections=[
                first_section,
                duplicate_claim_section,
            ],
            synthesis=synthesis,
            valid_reviewed_claim_ids=(
                valid_claim_ids
            ),
        ),
        description="Duplicate claim rejection",
    )

    empty_summary = deepcopy(
        synthesis
    )

    empty_summary.executive_summary = ""

    expect_rejection(
        action=lambda: assembler.assemble(
            plan=plan,
            generated_sections=[
                first_section,
                second_section,
            ],
            synthesis=empty_summary,
            valid_reviewed_claim_ids=(
                valid_claim_ids
            ),
        ),
        description="Empty summary rejection",
    )

    empty_conclusions = deepcopy(
        synthesis
    )

    empty_conclusions.conclusions = ""

    expect_rejection(
        action=lambda: assembler.assemble(
            plan=plan,
            generated_sections=[
                first_section,
                second_section,
            ],
            synthesis=empty_conclusions,
            valid_reviewed_claim_ids=(
                valid_claim_ids
            ),
        ),
        description="Empty conclusions rejection",
    )

    empty_limitation = deepcopy(
        synthesis
    )

    empty_limitation.limitations = [
        "",
    ]

    expect_rejection(
        action=lambda: assembler.assemble(
            plan=plan,
            generated_sections=[
                first_section,
                second_section,
            ],
            synthesis=empty_limitation,
            valid_reviewed_claim_ids=(
                valid_claim_ids
            ),
        ),
        description="Empty limitation rejection",
    )

    invalid_plan = deepcopy(
        plan
    )

    invalid_plan.sections[1].ordinal = 3

    expect_rejection(
        action=lambda: assembler.assemble(
            plan=invalid_plan,
            generated_sections=[
                first_section,
                second_section,
            ],
            synthesis=synthesis,
            valid_reviewed_claim_ids=(
                valid_claim_ids
            ),
        ),
        description="Nonconsecutive plan ordinal rejection",
    )

    print()
    print(
        "All report assembly tests: PASSED"
    )


if __name__ == "__main__":

    main()
