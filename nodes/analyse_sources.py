
from time import perf_counter

from sqlalchemy.orm import sessionmaker
from langchain_core.runnables import RunnableConfig

from agents.source_summariser import (
    SourceSummariser,
)

from application.execution_lease_heartbeat import (
    ExecutionLeaseLost,
)

from application.research_job_heartbeat import (
    ResearchJobLeaseLost,
)

from graph.state import ResearchState

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseFenceRejected,
)

from persistence.finding_repository import (
    FindingRepository,
)

from persistence.source_repository import (
    SourceRepository,
)

from processing.source_context_builder import (
    SourceContextBuilder,
)


class AnalyseSourcesNode:

    def __init__(
        self,
        session_factory: sessionmaker,
        summariser: SourceSummariser,
        context_builder: SourceContextBuilder,
    ):

        self.session_factory = session_factory
        self.summariser = summariser
        self.context_builder = context_builder

    def __call__(
        self,
        state: ResearchState,
        config: RunnableConfig,
    ) -> dict:

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

        session_id = state["session_id"]

        if lease.session_id != session_id:

            raise ValueError(
                "Execution lease does not match "
                "the research session."
            )

        question_id = state[
            "current_question_id"
        ]

        question = state[
            "current_question"
        ]

        if question_id is None:

            raise ValueError(
                "No research question selected."
            )

        if question is None:

            raise ValueError(
                "Research question text is missing."
            )

        if execution_guard is not None:

            execution_guard()

        with self.session_factory() as db:

            source_repository = SourceRepository(db)

            sources = (
                source_repository.get_for_question(
                    question_id
                )
            )

        print()
        print(
            f"Analysing {len(sources)} sources "
            f"for question {question_id}"
        )

        for index, source in enumerate(
            sources,
            start=1,
        ):

            if execution_guard is not None:

                execution_guard()

            try:

                with self.session_factory() as db:

                    finding_repository = FindingRepository(
                        db
                    )

                    if finding_repository.analysis_exists(
                        source_id=source.id,
                        question_id=question_id,
                    ):

                        print(
                            f"Skipping source {source.id}: "
                            "already analysed."
                        )

                        continue

                print()
                print(
                    f"Analysing source "
                    f"{index}/{len(sources)}"
                )

                print(
                    f"Source ID: {source.id}"
                )

                print(
                    f"Title: {source.title}"
                )

                print(
                    f"Text length: "
                    f"{len(source.extracted_text):,}"
                )

                context, chunk_count, selected_count = (
                    self.context_builder.build(
                        question=question,
                        source_text=source.extracted_text,
                    )
                )

                print(
                    f"Document chunks: {chunk_count}"
                )

                print(
                    f"Selected chunks: {selected_count}"
                )

                print(
                    f"Context length: "
                    f"{len(context):,} chars"
                )

                if execution_guard is not None:

                    execution_guard()

                started = perf_counter()

                analysis = self.summariser.analyse(
                    research_question=question,
                    source_title=source.title,
                    source_url=source.final_url,
                    source_text=context,
                )

                if execution_guard is not None:

                    execution_guard()

                elapsed = perf_counter() - started

                print(
                    f"Model completed in "
                    f"{elapsed:.1f} seconds."
                )

                print(
                    f"Model returned "
                    f"{len(analysis.findings)} findings."
                )

                with self.session_factory() as db:

                    finding_repository = FindingRepository(
                        db
                    )

                    finding_repository.save_analysis(
                        source_id=source.id,
                        question_id=question_id,
                        analysis=analysis,
                        lease=lease,
                    )

                print(
                    f"Source {source.id} analysis saved."
                )

            except (
                ExecutionLeaseFenceRejected,
                ExecutionLeaseLost,
                ResearchJobLeaseLost,
            ):

                raise

            except Exception as ex:

                print(
                    f"Failed to analyse source "
                    f"{source.id}: "
                    f"{type(ex).__name__}: {ex}"
                )

        if execution_guard is not None:

            execution_guard()

        print()
        print("Source analysis complete.")

        return {}
