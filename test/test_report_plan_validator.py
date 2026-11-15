
from domain.report_plan import (
    ProposedReportPlan,
    ProposedReportSection,
)

from processing.report_plan_validator import (
    ReportPlanValidator,
)


def main():

    proposed_plan = ProposedReportPlan(
        title="Example Research Report",
        sections=[
            ProposedReportSection(
                heading="Background",
                purpose="Establish the relevant background.",
                reviewed_claim_ids=[10, 11],
            ),
            ProposedReportSection(
                heading="Technical Evidence",
                purpose="Examine the reviewed technical evidence.",
                reviewed_claim_ids=[11, 12, 12],
            ),
            ProposedReportSection(
                heading="Evidence Gaps",
                purpose="Discuss unresolved research questions.",
                reviewed_claim_ids=[],
            ),
        ],
    )

    validator = (
        ReportPlanValidator()
    )

    valid_claim_ids = {
        10,
        11,
        12,
    }

    validator.validate_claim_references(
        plan=proposed_plan,
        valid_reviewed_claim_ids=valid_claim_ids,
    )

    report_plan = (
        validator.allocate_word_counts(
            proposed_plan=proposed_plan,
            target_word_count=15000,
        )
    )

    total_words = (
        report_plan.executive_summary_word_count
        + report_plan.conclusions_word_count
        + report_plan.limitations_word_count
    )

    for section in report_plan.sections:

        total_words += (
            section.target_word_count
        )

    assert total_words == 15000

    assert [
        section.ordinal
        for section in report_plan.sections
    ] == [1, 2, 3]

    assert (
        report_plan.sections[1].reviewed_claim_ids
        == [11, 12]
    )

    assert (
        report_plan.sections[2].reviewed_claim_ids
        == []
    )

    print("Report planning validation passed.")

    print()
    print(f"Report: {report_plan.title}")
    print(f"Target words: {report_plan.target_word_count}")

    print()
    print(
        "Executive summary: "
        f"{report_plan.executive_summary_word_count}"
    )

    for section in report_plan.sections:

        print()
        print(
            f"{section.ordinal}. {section.heading}"
        )

        print(
            f"Target words: {section.target_word_count}"
        )

        print(
            "Reviewed claim IDs: "
            f"{section.reviewed_claim_ids}"
        )

    print()
    print(
        "Conclusions: "
        f"{report_plan.conclusions_word_count}"
    )

    print(
        "Limitations: "
        f"{report_plan.limitations_word_count}"
    )


if __name__ == "__main__":

    main()
