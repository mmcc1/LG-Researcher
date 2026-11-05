from sqlalchemy.orm import sessionmaker

from extraction.html import HtmlDocumentExtractor
from graph.state import ResearchState
from persistence.search_repository import (
    SearchRepository,
)
from persistence.source_repository import (
    SourceRepository,
)
from retrieval.base import DocumentRetriever

from langchain_core.runnables import RunnableConfig

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseFenceRejected,
)


class RetrieveSourcesNode:

    def __init__(
        self,
        session_factory: sessionmaker,
        retriever: DocumentRetriever,
        extractor: HtmlDocumentExtractor,
        max_sources: int = 5,
    ):
        self.session_factory = session_factory
        self.retriever = retriever
        self.extractor = extractor
        self.max_sources = max_sources

    def __call__(
        self,
        state: ResearchState,
        config: RunnableConfig,
    ) -> dict:

        question_id = state[
            "current_question_id"
        ]

        
        session_id = state["session_id"]

        lease = config.get(
            "configurable",
            {},
        ).get(
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


        if question_id is None:
            raise ValueError(
                "No research question selected."
            )

        attempt_id = state.get(
            "current_search_attempt_id"
        )

        #
        # Load discovered search results.
        #
        # New SearchAttempt-aware workflow paths
        # retrieve only results belonging to the
        # current discovery pass.
        #
        # The legacy fallback supports historical
        # sessions whose WebSearchResult rows
        # predate SearchAttempt provenance.
        #

        with self.session_factory() as db:

            search_repository = (
                SearchRepository(db)
            )

            if attempt_id is not None:

                search_results = (
                    search_repository
                    .get_results_for_attempt(
                        attempt_id
                    )
                )

                print(
                    "Loading search results for "
                    f"attempt {attempt_id}."
                )

            else:

                search_results = (
                    search_repository
                    .get_results_for_question(
                        question_id
                    )
                )

                print(
                    "No search attempt is associated "
                    "with this research pass. "
                    "Using legacy question-level "
                    "search results."
                )

        #
        # Deduplicate URLs while preserving
        # search-result ordering.
        #

        seen_urls = set()
        unique_urls = []

        for result in search_results:

            #
            # Defensive provenance check.
            #
            # Even though get_results_for_attempt()
            # scopes by attempt ID, every result
            # should still belong to the current
            # question and session.
            #

            if (
                result.research_question_id
                != question_id
            ):
                raise ValueError(
                    "Search result does not belong "
                    "to the current research "
                    "question."
                )

            if (
                result.research_session_id
                != state["session_id"]
            ):
                raise ValueError(
                    "Search result does not belong "
                    "to the current research "
                    "session."
                )

            url = result.url.strip()

            if not url:
                continue

            normalized = url.lower()

            if normalized in seen_urls:
                continue

            seen_urls.add(
                normalized
            )

            unique_urls.append(
                url
            )

        #
        # Retrieve sources.
        #

        retrieved_count = 0

        for url in unique_urls:

            if (
                retrieved_count
                >= self.max_sources
            ):
                break

            #
            # Persistent source deduplication remains
            # session-wide.
            #
            # This is important for deeper research:
            # if the new search rediscovers a URL
            # already retrieved by an earlier pass,
            # we do not download/store it again.
            #

            with self.session_factory() as db:

                source_repository = (
                    SourceRepository(db)
                )

                if (
                    source_repository
                    .exists_for_url(
                        state["session_id"],
                        url,
                    )
                ):
                    continue

            try:

                retrieved = (
                    self.retriever.retrieve(
                        url
                    )
                )

                document = (
                    self.extractor.extract(
                        retrieved
                    )
                )

                with self.session_factory() as db:

                    source_repository = (
                        SourceRepository(db)
                    )

                    source_repository.save(
                        session_id=state[
                            "session_id"
                        ],
                        question_id=question_id,
                        document=document,
                        lease=lease,
                    )

                retrieved_count += 1

            except ExecutionLeaseFenceRejected:

                raise

            except Exception as ex:

                print(
                    f"Failed to retrieve source "
                    f"{url}: {ex}"
                )

        return {}