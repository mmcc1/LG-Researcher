
from time import perf_counter

from agents.report_section_agent import (
    ReportSectionAgent,
)

from agents.report_synthesis_agent import (
    ReportSynthesisAgent,
)

from config import settings

from domain.report_plan import (
    PlannedReportSection,
    ReportPlan,
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

from processing.report_synthesis_validator import (
    ReportSynthesisValidator,
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

    report_plan = ReportPlan(
        title=(
            "The Latest Advancements in Dentistry"
        ),
        target_word_count=300,
        executive_summary_word_count=50,
        conclusions_word_count=40,
        limitations_word_count=23,
        sections=[
            planned_section,
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
    print(
        "REPORT SYNTHESIS GENERATION TEST"
    )
    print()

    print(
        f"Topic: {topic}"
    )

    print(
        f"Section: {planned_section.heading}"
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

    section_agent = ReportSectionAgent(
        model=model
    )

    synthesis_agent = ReportSynthesisAgent(
        model=model
    )

    section_validator = ReportSectionValidator()

    synthesis_validator = (
        ReportSynthesisValidator()
    )

    print()
    print(
        "Generating report section...",
        flush=True,
    )

    section_start_time = perf_counter()

    generated_section = section_agent.generate(
        topic=topic,
        section=planned_section,
        reviewed_evidence=reviewed_evidence,
    )

    section_elapsed_seconds = (
        perf_counter()
        - section_start_time
    )

    section_validation = section_validator.validate(
        section=generated_section,
        planned_section=planned_section,
    )

    print()
    print(
        "Section generation completed in "
        f"{section_elapsed_seconds:.1f} seconds."
    )

    print(
        "Generated section words: "
        f"{section_validation.actual_word_count}"
    )

    print(
        "Section structural validation: PASSED"
    )

    print()
    print(
        "Generating final synthesis...",
        flush=True,
    )

    synthesis_start_time = perf_counter()

    synthesis = synthesis_agent.generate(
        topic=topic,
        plan=report_plan,
        sections=[
            generated_section,
        ],
        reviewed_evidence=reviewed_evidence,
    )

    synthesis_elapsed_seconds = (
        perf_counter()
        - synthesis_start_time
    )

    validation = synthesis_validator.validate(
        synthesis=synthesis,
        plan=report_plan,
    )

    print()
    print(
        "Synthesis generation completed in "
        f"{synthesis_elapsed_seconds:.1f} seconds."
    )

    print()
    print(
        "SYNTHESIS VALIDATION"
    )
    print()

    print(
        "Executive summary words: "
        f"{validation.executive_summary_word_count}"
    )

    print(
        "Conclusions words: "
        f"{validation.conclusions_word_count}"
    )

    print(
        "Limitations words: "
        f"{validation.limitations_word_count}"
    )

    print(
        "Total synthesis words: "
        f"{validation.total_word_count}"
    )

    print()
    print(
        "EXECUTIVE SUMMARY"
    )
    print()

    print(
        synthesis.executive_summary
    )

    print()
    print(
        "CONCLUSIONS"
    )
    print()

    print(
        synthesis.conclusions
    )

    print()
    print(
        "LIMITATIONS"
    )
    print()

    if synthesis.limitations:

        for index, limitation in enumerate(
            synthesis.limitations,
            start=1,
        ):

            print(
                f"{index}. {limitation}"
            )

    else:

        print(
            "No limitations were returned."
        )

    print()
    print(
        "Synthesis structural validation: PASSED"
    )


if __name__ == "__main__":

    main()
