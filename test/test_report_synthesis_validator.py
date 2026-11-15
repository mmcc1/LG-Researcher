
from domain.report_plan import (
    PlannedReportSection,
    ReportPlan,
)

from domain.report_synthesis import ReportSynthesis

from processing.report_synthesis_validator import (
    ReportSynthesisValidator,
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
                heading="Test Section",
                purpose="Examine the available evidence.",
                target_word_count=870,
                reviewed_claim_ids=[
                    1,
                ],
            ),
        ],
    )

    validator = ReportSynthesisValidator()

    synthesis = ReportSynthesis(
        executive_summary=(
            "The research identifies several findings "
            "supported by the reviewed evidence."
        ),
        conclusions=(
            "The available evidence supports a limited "
            "set of conclusions."
        ),
        limitations=[
            "Some evidence remains incomplete.",
            "Certain findings require further verification.",
        ],
    )

    result = validator.validate(
        synthesis=synthesis,
        plan=plan,
    )

    if result.executive_summary_word_count <= 0:

        raise AssertionError(
            "Executive summary word count is invalid."
        )

    if result.conclusions_word_count <= 0:

        raise AssertionError(
            "Conclusions word count is invalid."
        )

    if result.limitations_word_count <= 0:

        raise AssertionError(
            "Limitations word count is invalid."
        )

    print()
    print(
        "REPORT SYNTHESIS VALIDATION TEST"
    )

    print(
        "Executive summary words:",
        result.executive_summary_word_count,
    )

    print(
        "Conclusions words:",
        result.conclusions_word_count,
    )

    print(
        "Limitations words:",
        result.limitations_word_count,
    )

    print(
        "Total synthesis words:",
        result.total_word_count,
    )

    print(
        "Valid synthesis: PASSED"
    )

    invalid_synthesis = ReportSynthesis(
        executive_summary="",
        conclusions="Valid conclusions.",
        limitations=[],
    )

    try:

        validator.validate(
            synthesis=invalid_synthesis,
            plan=plan,
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

        validator.validate(
            synthesis=invalid_synthesis,
            plan=plan,
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

        validator.validate(
            synthesis=invalid_synthesis,
            plan=plan,
        )

    except ValueError:

        print(
            "Empty limitation rejection: PASSED"
        )

    else:

        raise AssertionError(
            "Empty limitation was accepted."
        )

    print()
    print(
        "All report synthesis validation tests: PASSED"
    )


if __name__ == "__main__":

    main()
