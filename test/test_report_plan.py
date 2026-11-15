
#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

import argparse
from time import perf_counter

from agents.report_agent import (
    ReportAgent,
)

from config import settings

from models.factory import (
    ChatModelFactory,
)

from persistence.database import (
    SessionLocal,
)

from persistence.models import (
    ResearchSession,
)

from persistence.research_scope_repository import (
    ResearchScopeRepository,
)

from persistence.review_repository import (
    ReviewRepository,
)

from processing.report_context_builder import (
    ReportContextBuilder,
)


def load_research_material(
    session_id: str,
):

    with SessionLocal() as db:

        research_session = db.get(
            ResearchSession,
            session_id,
        )

        if research_session is None:

            raise ValueError(
                "Research session was not found."
            )

        review_repository = ReviewRepository(
            db
        )

        scope_repository = ResearchScopeRepository(
            db
        )

        reviews = review_repository.get_for_session(
            session_id
        )

        scope_definition = scope_repository.get(
            session_id
        )

        topic = research_session.topic

    if not reviews:

        raise ValueError(
            "Research session contains no "
            "persisted reviews."
        )

    return (
        topic,
        reviews,
        scope_definition,
    )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Test report planning using persisted "
            "reviewed research evidence."
        )
    )

    parser.add_argument(
        "session_id",
        help="Existing research session ID.",
    )

    arguments = parser.parse_args()

    session_id = arguments.session_id

    (
        topic,
        reviews,
        scope_definition,
    ) = load_research_material(
        session_id
    )

    context_builder = ReportContextBuilder()

    reviewed_evidence = context_builder.build(
        reviews
    )

    valid_reviewed_claim_ids = {
        claim.id
        for review in reviews
        for claim in review.reviewed_claims
    }

    print()
    print("REPORT PLANNING TEST")
    print()

    print(
        f"Research session: {session_id}"
    )

    print(
        f"Topic: {topic}"
    )

    print(
        f"Persisted reviews: {len(reviews):,}"
    )

    print(
        "Reviewed claims: "
        f"{len(valid_reviewed_claim_ids):,}"
    )

    print(
        "Evidence context length: "
        f"{len(reviewed_evidence):,} characters"
    )

    print(
        "Structured scope available: "
        f"{scope_definition is not None}"
    )

    print()
    print(
        "Initializing reporting model...",
        flush=True,
    )

    model = ChatModelFactory.create(
        settings.reporter_model
    )

    report_agent = ReportAgent(
        model=model
    )

    print(
        "Generating report plan...",
        flush=True,
    )

    start_time = perf_counter()

    report_plan = report_agent.plan(
        topic=topic,
        reviewed_evidence=reviewed_evidence,
        valid_reviewed_claim_ids=(
            valid_reviewed_claim_ids
        ),
        scope_definition=scope_definition,
    )

    elapsed_seconds = (
        perf_counter()
        - start_time
    )

    print()
    print(
        "Report planning completed in "
        f"{elapsed_seconds:.1f} seconds."
    )

    print()
    print(
        f"Proposed title: {report_plan.title}"
    )

    print(
        "Target word count: "
        f"{report_plan.target_word_count:,}"
    )

    print(
        "Executive summary words: "
        f"{report_plan.executive_summary_word_count:,}"
    )

    print(
        "Conclusions words: "
        f"{report_plan.conclusions_word_count:,}"
    )

    print(
        "Limitations words: "
        f"{report_plan.limitations_word_count:,}"
    )

    print()
    print("PLANNED SECTIONS")
    print()

    allocated_claim_ids = set()

    for section in report_plan.sections:

        print(
            f"{section.ordinal}. {section.heading}"
        )

        print(
            "Purpose: "
            f"{section.purpose}"
        )

        print(
            "Target words: "
            f"{section.target_word_count:,}"
        )

        print(
            "Reviewed claim IDs: "
            f"{section.reviewed_claim_ids}"
        )

        allocated_claim_ids.update(
            section.reviewed_claim_ids
        )

        print()

    unallocated_claim_ids = (
        valid_reviewed_claim_ids
        - allocated_claim_ids
    )

    print("PLAN COVERAGE")
    print()

    print(
        "Available reviewed claims: "
        f"{len(valid_reviewed_claim_ids):,}"
    )

    print(
        "Allocated reviewed claims: "
        f"{len(allocated_claim_ids):,}"
    )

    print(
        "Unallocated reviewed claims: "
        f"{len(unallocated_claim_ids):,}"
    )

    if unallocated_claim_ids:

        print(
            "Unallocated claim IDs: "
            f"{sorted(unallocated_claim_ids)}"
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

    assert total_words == (
        report_plan.target_word_count
    )

    assert allocated_claim_ids.issubset(
        valid_reviewed_claim_ids
    )

    print()
    print(
        "Report plan validation: PASSED"
    )


if __name__ == "__main__":

    main()
