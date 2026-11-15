
from domain.report import (
    ReportSection,
)

from domain.report_plan import (
    PlannedReportSection,
)

from processing.report_section_validator import (
    ReportSectionValidator,
)


def main():

    planned_section = PlannedReportSection(
        ordinal=1,
        heading="Digital Dental Technologies",
        purpose=(
            "Examine the reviewed evidence concerning "
            "digital technologies in dentistry."
        ),
        target_word_count=200,
        reviewed_claim_ids=[
            336,
            337,
            338,
        ],
    )

    generated_section = ReportSection(
        heading="Digital Dental Technologies",
        content=(
            "The reviewed evidence describes the use "
            "of digital technologies in dental workflows. "
            "Several findings concern customized "
            "prosthetics and implant design. "
            "The strength of the conclusions depends "
            "on the available clinical evidence."
        ),
        reviewed_claim_ids=[
            336,
            337,
        ],
    )

    validator = ReportSectionValidator()

    result = validator.validate(
        section=generated_section,
        planned_section=planned_section,
    )

    assert result.actual_word_count > 0

    assert result.target_word_count == 200

    assert result.referenced_claim_count == 2

    print(
        "Valid section: PASSED"
    )

    print(
        "Actual words: "
        f"{result.actual_word_count}"
    )

    print(
        "Target words: "
        f"{result.target_word_count}"
    )

    print(
        "Word count ratio: "
        f"{result.word_count_ratio:.2f}"
    )

    invalid_section = ReportSection(
        heading="Digital Dental Technologies",
        content="Controlled test content.",
        reviewed_claim_ids=[
            999999,
        ],
    )

    try:

        validator.validate(
            section=invalid_section,
            planned_section=planned_section,
        )

    except ValueError:

        print(
            "Invalid claim reference rejection: PASSED"
        )

    else:

        raise AssertionError(
            "Invalid reviewed claim reference "
            "was accepted."
        )


if __name__ == "__main__":

    main()
