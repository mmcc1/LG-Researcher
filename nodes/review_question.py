#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

from time import perf_counter

from sqlalchemy.orm import sessionmaker

from agents.review_agent import (
    ReviewAgent,
)

from graph.state import ResearchState

from persistence.finding_repository import (
    FindingRepository,
)

from persistence.review_repository import (
    ReviewRepository,
)

from persistence.source_repository import (
    SourceRepository,
)

from processing.review_context_builder import (
    ReviewContextBuilder,
)

from langchain_core.runnables import (
    RunnableConfig,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
)

from domain.review import (
    ResearchQuestionReview,
)


class ReviewQuestionNode:

    def __init__(
        self,
        session_factory: sessionmaker,
        review_agent: ReviewAgent,
        context_builder: ReviewContextBuilder,
    ):

        self.session_factory = (
            session_factory
        )

        self.review_agent = (
            review_agent
        )

        self.context_builder = (
            context_builder
        )

    def __call__(
        self,
        state: ResearchState,
        config: RunnableConfig,
    ) -> dict:

        question_id = (
            state[
                "current_review_question_id"
            ]
        )

        question_text = (
            state[
                "current_review_question"
            ]
        )

        if question_id is None:

            raise ValueError(
                "No review question is "
                "currently selected."
            )

        if question_text is None:

            raise ValueError(
                "No review question text is "
                "currently available."
            )

        session_id = state[
            "session_id"
        ]

        configurable = config.get(
            "configurable",
            {},
        )

        lease = configurable.get(
            "execution_lease"
        )

        if not isinstance(
            lease,
            ExecutionLease,
        ):

            raise RuntimeError(
                "Execution lease is missing "
                "from graph configuration."
            )

        if lease.session_id != session_id:

            raise ValueError(
                "Execution lease does not match "
                "the research session."
            )

        execution_guard = configurable.get(
            "execution_guard"
        )

        if (
            execution_guard is not None
            and not callable(execution_guard)
        ):

            raise TypeError(
                "Execution guard must be callable."
            )

        if execution_guard is not None:

            execution_guard()

        #
        # First load the evidence required by
        # the reviewer.
        #

        with self.session_factory() as db:

            review_repository = (
                ReviewRepository(db)
            )

            #
            # Recovery/idempotency case:
            #
            # The review may have been persisted
            # immediately before a process crash,
            # while the question was still marked
            # "reviewing".
            #

            if review_repository.exists_for_question(
                question_id
            ):

                review_id = (
                    review_repository
                    .save_review_fenced(
                        session_id=session_id,
                        question_id=question_id,
                        review=None,
                        valid_finding_ids=set(),
                        lease=lease,
                    )
                )

                if execution_guard is not None:

                    execution_guard()

                print(
                    "Review already exists for "
                    f"question {question_id}. "
                    f"Review ID: {review_id}. "
                    "Skipping Review Agent."
                )

                return {}

            finding_repository = (
                FindingRepository(db)
            )

            source_repository = (
                SourceRepository(db)
            )

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
                    f"research question {question_id}."
                )

                print(
                    "Persisting an insufficient-evidence "
                    "review without invoking the Review Agent."
                )

                review = ResearchQuestionReview(
                    answer=(
                        "Insufficient evidence to answer "
                        "the research question."
                    ),
                    reviewed_claims=[],
                    contradictions=[],
                    evidence_gaps=[
                        (
                            "No research findings were available "
                            "for this question."
                        )
                    ],
                    overall_confidence="low",
                    sufficient_evidence=False,
                )

                if execution_guard is not None:

                    execution_guard()

                review_id = (
                    review_repository.save_review_fenced(
                        session_id=session_id,
                        question_id=question_id,
                        review=review,
                        valid_finding_ids=set(),
                        lease=lease,
                    )
                )

                if execution_guard is not None:

                    execution_guard()

                print(
                    "Insufficient-evidence review persisted. "
                    f"Review ID: {review_id}"
                )

                return {}

            source_ids = {
                finding.source_id
                for finding in findings
            }

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

            findings_text = (
                self.context_builder.build(
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

        #
        # The database session is deliberately
        # closed before invoking the LLM.
        #
        # The Review Agent operates only on the
        # supplied plain-text evidence.
        #

        print()
        print(
            "Reviewing research question "
            f"{question_id}...",
            flush=True,
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
            f"Review context length: "
            f"{len(findings_text):,} chars"
        )

        #
        # Measure only the LLM invocation.
        #

        if execution_guard is not None:

            execution_guard()

        review_start = perf_counter()

        review = self.review_agent.review(
            research_question=(
                question_text
            ),
            findings_text=findings_text,
            valid_finding_ids=(
                valid_finding_ids
            ),
        )

        if execution_guard is not None:

            execution_guard()

        review_elapsed = (
            perf_counter()
            - review_start
        )

        print(
            "Review Agent completed in "
            f"{review_elapsed:.1f}s."
        )

        #
        # Persist the review.
        #
        # ReviewRepository performs deterministic
        # validation of all finding references.
        #

        persistence_start = perf_counter()

        with self.session_factory() as db:

            review_repository = (
                ReviewRepository(db)
            )

            review_id = (
                review_repository
                .save_review_fenced(
                    session_id=session_id,
                    question_id=question_id,
                    review=review,
                    valid_finding_ids=(
                        valid_finding_ids
                    ),
                    lease=lease,
                )
            )

            print(
                "Review persistence confirmed. "
                f"Review ID: {review_id}"
            )

        persistence_elapsed = (
            perf_counter()
            - persistence_start
        )

        print(
            "Review persistence completed in "
            f"{persistence_elapsed:.3f}s."
        )

        return {}
