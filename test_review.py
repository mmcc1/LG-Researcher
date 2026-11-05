from config import settings

from agents.review_agent import ReviewAgent

from models.factory import ChatModelFactory

from persistence.database import SessionLocal

from persistence.finding_repository import (
    FindingRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.source_repository import (
    SourceRepository,
)

from persistence.review_repository import (
    ReviewRepository,
)

from processing.review_context_builder import (
    ReviewContextBuilder,
)


def validate_finding_references(
    review,
    valid_finding_ids: set[int],
) -> list[int]:

    invalid_ids = set()

    for claim in review.reviewed_claims:

        referenced_ids = (
            claim.supporting_finding_ids
            + claim.contradicting_finding_ids
        )

        for finding_id in referenced_ids:

            if (
                finding_id
                not in valid_finding_ids
            ):

                invalid_ids.add(
                    finding_id
                )

    return sorted(
        invalid_ids
    )


def format_ids(
    ids: list[int],
) -> str:

    if not ids:
        return "None"

    return ", ".join(
        str(value)
        for value in ids
    )


def main():

    print("Review Agent Test")
    print("-----------------")
    print()

    question_id_text = input(
        "Enter research question ID: "
    ).strip()

    if not question_id_text:

        print(
            "A research question ID "
            "is required."
        )

        return

    try:

        question_id = int(
            question_id_text
        )

    except ValueError:

        print(
            "Research question ID "
            "must be an integer."
        )

        return

    #
    # Load the research question and
    # its extracted findings.
    #

    with SessionLocal() as db:

        research_repository = (
            ResearchSessionRepository(db)
        )

        finding_repository = (
            FindingRepository(db)
        )

        source_repository = (
            SourceRepository(db)
        )

        question = (
            research_repository.get_question(
                question_id
            )
        )

        if question is None:

            print()
            print(
                "Research question "
                "not found."
            )

            return

        findings = (
            finding_repository
            .get_for_question(
                question_id
            )
        )

        if not findings:

            print()
            print(
                "No findings exist for "
                "this research question."
            )

            return

        #
        # Determine which sources are
        # referenced by the findings.
        #

        source_ids = {
            finding.source_id
            for finding in findings
        }

        sources = (
            source_repository.get_by_ids(
                source_ids
            )
        )

        #
        # Convert the source collection
        # into an efficient lookup.
        #

        sources_by_id = {
            source.id: source
            for source in sources
        }

        #
        # Build the review context while
        # the SQLAlchemy objects are still
        # available.
        #

        context_builder = (
            ReviewContextBuilder()
        )

        findings_text = (
            context_builder.build(
                findings=findings,
                sources_by_id=sources_by_id,
            )
        )

        question_text = (
            question.question
        )

        #
        # Capture the valid finding IDs while
        # the database objects are available.
        #

        valid_finding_ids = {
            finding.id
            for finding in findings
        }

    #
    # SQL session is now closed.
    #
    # Everything below operates on plain
    # text/data and does not require DB access.
    #

    print()
    print("RESEARCH QUESTION")
    print("-----------------")
    print(question_text)

    print()
    print(
        f"Findings loaded: "
        f"{len(findings)}"
    )

    print(
        f"Sources represented: "
        f"{len(sources_by_id)}"
    )

    print(
        f"Review context length: "
        f"{len(findings_text):,} chars"
    )

    print(
        "Valid finding IDs: "
        + format_ids(
            sorted(valid_finding_ids)
        )
    )

    #
    # Create the reviewer model.
    #

    reviewer_model = (
        ChatModelFactory.create(
            settings.reviewer_model
        )
    )

    review_agent = ReviewAgent(
        model=reviewer_model
    )

    #
    # Perform the review.
    #

    print()
    print(
        "Invoking Review Agent...",
        flush=True,
    )

    try:

        review = review_agent.review(
            research_question=question_text,
            findings_text=findings_text,
        )

    except Exception as ex:

        print()
        print(
            "Review Agent failed:"
        )

        print(
            f"{type(ex).__name__}: "
            f"{ex}"
        )

        return

    #
    # Validate that every finding ID referenced
    # by the model was actually supplied to it.
    #

    invalid_finding_ids = (
        validate_finding_references(
            review=review,
            valid_finding_ids=valid_finding_ids,
        )
    )

    if invalid_finding_ids:

        print()
        print(
            "WARNING: Review Agent "
            "referenced finding IDs that "
            "were not supplied:"
        )

        print(
            ", ".join(
                str(value)
                for value
                in invalid_finding_ids
            )
        )

        print()
        print(
            "Review will NOT be persisted "
            "because provenance validation "
            "failed."
        )

        return

    else:

        print()
        print(
            "Finding reference validation: "
            "PASSED"
        )

    #
    # Display review.
    #

    print()
    print("REVIEW")
    print("------")

    print()
    print("ANSWER")
    print("------")
    print(review.answer)

    print()
    print("OVERALL CONFIDENCE")
    print("------------------")
    print(
        review.overall_confidence
    )

    print()
    print("SUFFICIENT EVIDENCE")
    print("-------------------")
    print(
        review.sufficient_evidence
    )

    print()
    print("REVIEWED CLAIMS")
    print("---------------")

    if not review.reviewed_claims:

        print()
        print("None.")

    for index, claim in enumerate(
        review.reviewed_claims,
        start=1,
    ):

        print()
        print(
            f"{index}. {claim.claim}"
        )

        print(
            f"   Confidence: "
            f"{claim.confidence}"
        )

        print(
            "   Supporting findings: "
            + format_ids(
                claim.supporting_finding_ids
            )
        )

        print(
            "   Contradicting findings: "
            + format_ids(
                claim.contradicting_finding_ids
            )
        )

    print()
    print("CONTRADICTIONS")
    print("--------------")

    if review.contradictions:

        for contradiction in (
            review.contradictions
        ):

            print()
            print(
                f"- {contradiction}"
            )

    else:

        print()
        print("None identified.")

    print()
    print("EVIDENCE GAPS")
    print("-------------")

    if review.evidence_gaps:

        for gap in review.evidence_gaps:

            print()
            print(
                f"- {gap}"
            )

    else:

        print()
        print("None identified.")

    #
    # Persist the review.
    #

    print()
    print(
        "Persisting review...",
        flush=True,
    )

    try:

        with SessionLocal() as db:

            review_repository = (
                ReviewRepository(db)
            )

            #
            # Do not create duplicate reviews
            # for the same research question.
            #

            if (
                review_repository
                .exists_for_question(
                    question_id
                )
            ):

                print()
                print(
                    "A persisted review "
                    "already exists for this "
                    "research question."
                )

                return

            persisted_review = (
                review_repository.save(
                    question_id=question_id,
                    review=review,
                    valid_finding_ids=(
                        valid_finding_ids
                    ),
                )
            )

            #
            # Capture the generated ID before
            # leaving the database session.
            #

            persisted_review_id = (
                persisted_review.id
            )

    except Exception as ex:

        print()
        print(
            "Review persistence failed:"
        )

        print(
            f"{type(ex).__name__}: "
            f"{ex}"
        )

        return

    print()
    print(
        "Review persisted successfully."
    )

    print(
        f"Question review ID: "
        f"{persisted_review_id}"
    )


if __name__ == "__main__":
    main()