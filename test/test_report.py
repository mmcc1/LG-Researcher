from time import perf_counter

from agents.report_agent import ReportAgent
from models.agent_models import AgentModels
from persistence.database import SessionLocal
from persistence.review_repository import (
    ReviewRepository,
)
from processing.report_context_builder import (
    ReportContextBuilder,
)
from processing.report_validator import (
    ReportValidator,
)
from models.factory import ChatModelFactory
from config import settings

SESSION_ID = (
    "063bd913-9e9a-48bd-81d7-8738153a7863"
)

TOPIC = "What is Bitcoin?"


def main():

    #
    # Load the reviewed evidence.
    #

    with SessionLocal() as db:

        repository = ReviewRepository(db)

        reviews = repository.get_for_session(
            SESSION_ID
        )

    if not reviews:

        raise RuntimeError(
            "No persisted reviews were found."
        )

    #
    # Build the report context.
    #

    context_builder = (
        ReportContextBuilder()
    )

    reviewed_evidence = (
        context_builder.build(
            reviews
        )
    )

    #
    # Construct the set of reviewed claim IDs
    # that the Report Agent is allowed to use.
    #

    valid_reviewed_claim_ids = {
        claim.id
        for review in reviews
        for claim in review.reviewed_claims
    }

    print(
        f"Reviews loaded: {len(reviews)}"
    )

    print(
        "Reviewed claims available: "
        f"{len(valid_reviewed_claim_ids)}"
    )

    print(
        "Report context length: "
        f"{len(reviewed_evidence):,} chars"
    )

    #
    # Create the model and Report Agent.
    #
    # Use the existing AgentModels construction
    # pattern from your project here.
    #

    models = AgentModels(

        planner=ChatModelFactory.create(
            settings.planner_model
        ),

        researcher=ChatModelFactory.create(
            settings.researcher_model
        ),

        summariser=ChatModelFactory.create(
            settings.summariser_model
        ),

        reviewer=ChatModelFactory.create(
            settings.reviewer_model
        ),

        reporter=ChatModelFactory.create(
            settings.reporter_model
        ),

        controller=ChatModelFactory.create(
            settings.controller_model
        ),
    )

    report_agent = ReportAgent(
        model=models.reporter
    )

    print()
    print(
        "Generating research report...",
        flush=True,
    )

    start = perf_counter()

    report = report_agent.generate(
        topic=TOPIC,
        reviewed_evidence=reviewed_evidence,
    )

    elapsed = (
        perf_counter() - start
    )

    print(
        "Report Agent completed in "
        f"{elapsed:.1f}s."
    )

    #
    # Deterministically validate provenance.
    #

    validator = ReportValidator()

    validator.validate_claim_references(
        report=report,
        valid_reviewed_claim_ids=(
            valid_reviewed_claim_ids
        ),
    )

    print(
        "Report provenance validation passed."
    )

    print()
    print("=" * 70)
    print(report.title)
    print("=" * 70)

    print()
    print("EXECUTIVE SUMMARY")
    print()
    print(
        report.executive_summary
    )

    for section in report.sections:

        print()
        print("-" * 70)
        print(section.heading)
        print("-" * 70)
        print()
        print(section.content)
        print()
        print(
            "Reviewed claim IDs: "
            + ", ".join(
                str(claim_id)
                for claim_id
                in section.reviewed_claim_ids
            )
        )

    print()
    print("-" * 70)
    print("CONCLUSIONS")
    print("-" * 70)
    print()
    print(report.conclusions)

    print()
    print("-" * 70)
    print("LIMITATIONS")
    print("-" * 70)

    for limitation in (
        report.limitations
    ):

        print(
            f"- {limitation}"
        )


if __name__ == "__main__":

    main()