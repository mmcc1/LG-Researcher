
from time import perf_counter

from sqlalchemy.orm import sessionmaker

from agents.report_agent import (
    ReportAgent,
)

from graph.state import (
    ResearchState,
)

from persistence.report_repository import (
    ReportRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.review_repository import (
    ReviewRepository,
)

from processing.report_context_builder import (
    ReportContextBuilder,
)

from processing.report_validator import (
    ReportValidator,
)

from langchain_core.runnables import (
    RunnableConfig,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
)


class GenerateReportNode:

    def __init__(
        self,
        session_factory: sessionmaker,
        report_agent: ReportAgent,
        context_builder: ReportContextBuilder,
        validator: ReportValidator,
    ):

        self.session_factory = (
            session_factory
        )

        self.report_agent = (
            report_agent
        )

        self.context_builder = (
            context_builder
        )

        self.validator = (
            validator
        )

    def __call__(
        self,
        state: ResearchState,
        config: RunnableConfig,
    ) -> dict:

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

        topic = state[
            "topic"
        ]

        #
        # -------------------------------------------------
        # Recovery / idempotency check
        # -------------------------------------------------
        #
        # If a previous execution successfully persisted
        # the report but terminated before marking the
        # research session completed, do not invoke the
        # Report Agent again.
        #

        with self.session_factory() as db:

            report_repository = (
                ReportRepository(db)
            )

            if report_repository.exists_for_session(
                session_id
            ):

                report_id = (
                    report_repository
                    .save_report_fenced(
                        session_id=session_id,
                        report=None,
                        lease=lease,
                    )
                )

                if execution_guard is not None:

                    execution_guard()

                print()
                print(
                    "Research report already exists. "
                    f"Report ID: {report_id}"
                )

                print(
                    "Skipping Report Agent."
                )

                return {}

        #
        # -------------------------------------------------
        # Workflow integrity check
        # -------------------------------------------------
        #
        # A final report must not be generated while
        # research questions are still waiting for
        # review.
        #

        with self.session_factory() as db:

            session_repository = (
                ResearchSessionRepository(db)
            )

            if (
                session_repository
                .has_unfinished_research_questions(
                    session_id
                )
            ):

                raise RuntimeError(
                    "Cannot generate final report "
                    "because one or more research "
                    "questions have not completed "
                    "research."
                )

            if (
                session_repository
                .has_unfinished_review_questions(
                    session_id
                )
            ):

                raise RuntimeError(
                    "Cannot generate final report "
                    "because one or more research "
                    "questions have not completed "
                    "review."
                )

        #
        # -------------------------------------------------
        # Mark reporting as started
        # -------------------------------------------------
        #
        # Persist this BEFORE invoking the LLM.
        #
        # If the process terminates while the Report
        # Agent is running, resume will see:
        #
        #     status = reporting
        #
        # with no persisted report and will safely
        # regenerate it.
        #

        if execution_guard is not None:

            execution_guard()

        with self.session_factory() as db:

            session_repository = (
                ResearchSessionRepository(db)
            )

            session_repository.begin_reporting_fenced(
                session_id=session_id,
                lease=lease,
            )

        #
        # -------------------------------------------------
        # Load reviewed research material
        # -------------------------------------------------
        #

        with self.session_factory() as db:

            review_repository = (
                ReviewRepository(db)
            )

            reviews = (
                review_repository
                .get_for_session(
                    session_id
                )
            )

        if not reviews:

            raise RuntimeError(
                "Cannot generate report because "
                "the research session contains "
                "no persisted reviews."
            )

        #
        # Build the reviewed evidence package supplied
        # to the Report Agent.
        #

        reviewed_evidence = (
            self.context_builder.build(
                reviews
            )
        )

        #
        # These are the provenance IDs actually supplied
        # to the model.
        #

        valid_reviewed_claim_ids = {
            claim.id
            for review in reviews
            for claim in review.reviewed_claims
        }

        print()
        print(
            "Generating final research report...",
            flush=True,
        )

        print(
            f"Reviews: {len(reviews):,}"
        )

        print(
            "Reviewed claims: "
            f"{len(valid_reviewed_claim_ids):,}"
        )

        print(
            "Report context length: "
            f"{len(reviewed_evidence):,} chars"
        )

        #
        # -------------------------------------------------
        # Report Agent
        # -------------------------------------------------
        #

        if execution_guard is not None:

            execution_guard()

        report_start = (
            perf_counter()
        )

        report = (
            self.report_agent.generate(
                topic=topic,
                reviewed_evidence=(
                    reviewed_evidence
                ),
            )
        )

        if execution_guard is not None:

            execution_guard()

        report_elapsed = (
            perf_counter()
            - report_start
        )

        print(
            "Report Agent completed in "
            f"{report_elapsed:.1f}s."
        )

        #
        # -------------------------------------------------
        # Model-output provenance validation
        # -------------------------------------------------
        #
        # Verify that the Report Agent referenced only
        # reviewed claims actually supplied in its
        # evidence context.
        #

        self.validator.validate_claim_references(
            report=report,
            valid_reviewed_claim_ids=(
                valid_reviewed_claim_ids
            ),
        )

        print(
            "Report provenance validation passed."
        )

        if execution_guard is not None:

            execution_guard()

        #
        # -------------------------------------------------
        # Persistence
        # -------------------------------------------------
        #
        # Use another short-lived database session.
        #
        # Check again immediately before persistence.
        # This is useful for recovery and future
        # concurrent execution.
        #

        persistence_start = (
            perf_counter()
        )

        with self.session_factory() as db:

            report_repository = (
                ReportRepository(db)
            )

            report_id = (
                report_repository
                .save_report_fenced(
                    session_id=session_id,
                    report=report,
                    lease=lease,
                )
            )

            print(
                "Report persistence confirmed. "
                f"Report ID: {report_id}"
            )

        persistence_elapsed = (
            perf_counter()
            - persistence_start
        )

        print(
            "Report persistence completed in "
            f"{persistence_elapsed:.3f}s."
        )

        return {}
