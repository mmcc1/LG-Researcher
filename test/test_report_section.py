
from time import perf_counter

from agents.report_section_agent import (
    ReportSectionAgent,
)

from config import settings

from domain.report_plan import (
    PlannedReportSection,
)

from models.factory import (
    ChatModelFactory,
)

from persistence.database import (
    SessionLocal,
)

from persistence.models import (
    ResearchSession,
)

from persistence.review_repository import (
    ReviewRepository,
)

from processing.report_section_context_builder import (
    ReportSectionContextBuilder,
)

from processing.report_section_validator import (
    ReportSectionValidator,
)


def main():

    session_id = (
        "016e665d-ebf9-4c23-a640-80196506ecbe"
    )

    planned_section = PlannedReportSection(
        ordinal=1,
        heading=(
            "Digital Innovations in Dental "
            "Prosthetics and Implants"
        ),
        purpose=(
            "Examine how 3D printing and CAD/CAM "
            "technologies are transforming customized "
            "dental prosthetics and implant designs, "
            "including their impact on precision, "
            "material properties, and clinical workflows."
        ),
        target_word_count=187,
        reviewed_claim_ids=[
            336,
            337,
            338,
        ],
    )

    with SessionLocal() as db:

        research_session = db.get(
            ResearchSession,
            session_id,
        )

        if research_session is None:

            raise ValueError(
                "Research session was not found."
            )

        topic = research_session.topic

        review_repository = ReviewRepository(
            db
        )

        reviews = review_repository.get_for_session(
            session_id
        )

    if not reviews:

        raise ValueError(
            "No persisted reviews were found."
        )

    context_builder = (
        ReportSectionContextBuilder()
    )

    reviewed_evidence = context_builder.build(
        reviews=reviews,
        section=planned_section,
    )

    print()
    print("REPORT SECTION GENERATION TEST")
    print()

    print(
        f"Topic: {topic}"
    )

    print(
        f"Section: {planned_section.heading}"
    )

    print(
        "Target words: "
        f"{planned_section.target_word_count}"
    )

    print(
        "Allocated reviewed claims: "
        f"{planned_section.reviewed_claim_ids}"
    )

    print(
        "Evidence context length: "
        f"{len(reviewed_evidence):,} characters"
    )

    print()
    print(
        "Initializing reporting model...",
        flush=True,
    )

    model = ChatModelFactory.create(
        settings.reporter_model
    )

    agent = ReportSectionAgent(
        model=model
    )

    validator = ReportSectionValidator()

    print(
        "Generating section...",
        flush=True,
    )

    start_time = perf_counter()

    generated_section = agent.generate(
        topic=topic,
        section=planned_section,
        reviewed_evidence=reviewed_evidence,
    )

    elapsed_seconds = (
        perf_counter()
        - start_time
    )

    print()
    print(
        "Section generation completed in "
        f"{elapsed_seconds:.1f} seconds."
    )

    validation = validator.validate(
        section=generated_section,
        planned_section=planned_section,
    )

    print()
    print("SECTION VALIDATION")
    print()

    print(
        "Actual words: "
        f"{validation.actual_word_count}"
    )

    print(
        "Target words: "
        f"{validation.target_word_count}"
    )

    print(
        "Word count ratio: "
        f"{validation.word_count_ratio:.2f}"
    )

    print(
        "Referenced claims: "
        f"{validation.referenced_claim_count}"
    )

    print()
    print("GENERATED SECTION")
    print()

    print(
        generated_section.heading
    )

    print()

    print(
        generated_section.content
    )

    print()
    print(
        "Reviewed claim IDs: "
        f"{generated_section.reviewed_claim_ids}"
    )

    print()
    print(
        "Section structural validation: PASSED"
    )


if __name__ == "__main__":

    main()
