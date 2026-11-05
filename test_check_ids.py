from persistence.database import (
    SessionLocal,
)

from persistence.finding_repository import (
    FindingRepository,
)

from persistence.source_repository import (
    SourceRepository,
)

from processing.review_context_builder import (
    ReviewContextBuilder,
)


QUESTION_ID = 76

CHECK_IDS = [
    144,
    166,
    167,
    168,
    203,
    204,
]


with SessionLocal() as db:

    finding_repository = (
        FindingRepository(db)
    )

    source_repository = (
        SourceRepository(db)
    )

    #
    # Load exactly the same findings as
    # ReviewQuestionNode.
    #

    findings = (
        finding_repository
        .get_for_question(
            QUESTION_ID
        )
    )

    source_ids = {
        finding.source_id
        for finding in findings
    }

    #
    # Load exactly the same sources as
    # ReviewQuestionNode.
    #

    sources = (
        source_repository
        .get_by_ids(
            source_ids
        )
    )

    sources_by_id = {
        source.id: source
        for source in sources
    }

    #
    # Build exactly the same context as
    # ReviewQuestionNode.
    #

    context_builder = (
        ReviewContextBuilder()
    )

    findings_text = (
        context_builder.build(
            findings=findings,
            sources_by_id=(
                sources_by_id
            ),
        )
    )

    valid_finding_ids = {
        finding.id
        for finding in findings
    }


print(
    f"Question ID: "
    f"{QUESTION_ID}"
)

print(
    f"Findings: "
    f"{len(findings):,}"
)

print(
    f"Sources represented: "
    f"{len(source_ids):,}"
)

print(
    "Review context length: "
    f"{len(findings_text):,} chars"
)

print()

print(
    "Valid finding IDs:"
)

print(
    ", ".join(
        str(value)
        for value in sorted(
            valid_finding_ids
        )
    )
)

print()

print(
    "Context marker checks:"
)

for finding_id in CHECK_IDS:

    marker = (
        f"FINDING ID: {finding_id}"
    )

    print(
        f"{marker}: "
        f"{marker in findings_text}"
    )