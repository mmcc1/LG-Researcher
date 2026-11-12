from collections import Counter
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda
from sqlalchemy import inspect, text

from domain.finding import ExtractedFinding, SourceAnalysis
from domain.research_plan import ResearchPlan, ResearchQuestionPlan
from domain.search import SearchPlan, SearchQuery, SearchResult
from domain.web import RetrievedDocument
from extraction.html import HtmlDocumentExtractor
from graph.research_graph import create_research_graph
from persistence.database import SessionLocal
from persistence.research_session_repository import ResearchSessionRepository
from retrieval.base import DocumentRetriever
from search.base import SearchProvider

from test_search_result_fencing import create_session, delete_session
from test_review_completion_fencing import acquire_lease
from test_review_selection_fencing import set_session_status


TEST_URL = "https://example.org/deterministic-graph-test"
TEST_QUESTION = "What does the controlled evidence establish?"
TEST_CLAIM = "The controlled document identifies a deterministic test marker."


class FakeStructuredChatModel:

    def __init__(self):
        self.calls = Counter()
        self.constructed_schemas = set()

    def with_structured_output(self, schema, **kwargs):
        name = schema.__name__
        self.constructed_schemas.add(name)

        def respond(messages):
            self.calls[name] += 1

            if name == "ResearchPlan":
                return ResearchPlan(
                    topic="Deterministic graph integration test",
                    questions=[
                        ResearchQuestionPlan(
                            category="technical",
                            question=TEST_QUESTION,
                            rationale="Verify the production research pipeline.",
                        )
                    ],
                )

            if name == "SearchPlan":
                return SearchPlan(
                    queries=[
                        SearchQuery(
                            query="deterministic graph evidence marker",
                            rationale="Locate the controlled source.",
                        )
                    ]
                )

            if name == "SourceAnalysis":
                return SourceAnalysis(
                    summary="The source describes a deterministic test marker.",
                    findings=[
                        ExtractedFinding(
                            claim=TEST_CLAIM,
                            evidence=(
                                "The source explicitly states that the "
                                "deterministic test marker is present."
                            ),
                            relevance="Directly addresses the test question.",
                            confidence="high",
                        )
                    ],
                )

            raise AssertionError(
                f"Unexpected model invocation: {name}. "
                "Research-only execution must not invoke review/report models."
            )

        return RunnableLambda(respond)


class FakeSearchProvider(SearchProvider):

    def __init__(self):
        self.calls = []

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.calls.append((query, max_results))
        return [
            SearchResult(
                url=TEST_URL,
                title="Controlled Research Evidence",
                snippet="The deterministic test marker is present.",
                rank=1,
                query=query,
                provider="integration-test",
            )
        ]


class FakeDocumentRetriever(DocumentRetriever):

    def __init__(self):
        self.calls = []

    def retrieve(self, url: str) -> RetrievedDocument:
        self.calls.append(url)
        assert url == TEST_URL, f"Unexpected retrieval URL: {url}"

        html = """<!doctype html>
<html><head><title>Controlled Research Evidence</title></head>
<body><main><h1>Controlled Research Evidence</h1>
<p>The deterministic test marker is present.</p>
<p>This is locally supplied evidence for the LangGraph integration test.</p>
</main></body></html>"""

        return RetrievedDocument(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            content=html.encode("utf-8"),
        )


def prepare_session(session_id, lease):
    with SessionLocal() as db:
        repository = ResearchSessionRepository(db)
        repository.prepare_execution_fenced(
            session_id=session_id,
            lease=lease,
            resume=False,
        )


def get_status(session_id):
    with SessionLocal() as db:
        session = ResearchSessionRepository(db).get(session_id)
        assert session is not None, "Research session was not found."
        return session.status


def count_rows_for_session(
    table_name,
    session_id,
):

    with SessionLocal() as db:

        if table_name == "findings":

            return db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM dbo.findings AS f
                    INNER JOIN dbo.research_questions AS q
                        ON q.id = f.research_question_id
                    WHERE q.research_session_id = :session_id
                    """
                ),
                {"session_id": session_id},
            ).scalar_one()

        return db.execute(
            text(
                f"""
                SELECT COUNT(*)
                FROM dbo.[{table_name}]
                WHERE research_session_id = :session_id
                """
            ),
            {"session_id": session_id},
        ).scalar_one()


def cleanup_graph_test_session(
    session_id,
):

    with SessionLocal() as db:

        #
        # Delete findings associated with
        # the session's research questions.
        #

        db.execute(
            text(
                """
                DELETE FROM dbo.findings
                WHERE research_question_id IN (
                    SELECT id
                    FROM dbo.research_questions
                    WHERE research_session_id = :session_id
                )
                """
            ),
            {"session_id": session_id},
        )

        #
        # Delete source summaries before
        # deleting their parent sources.
        #

        db.execute(
            text(
                """
                DELETE FROM dbo.source_summaries
                WHERE source_id IN (
                    SELECT id
                    FROM dbo.sources
                    WHERE research_session_id = :session_id
                )
                """
            ),
            {"session_id": session_id},
        )

        #
        # Delete sources.
        #

        db.execute(
            text(
                """
                DELETE FROM dbo.sources
                WHERE research_session_id = :session_id
                """
            ),
            {"session_id": session_id},
        )

        db.commit()

    #
    # Existing cleanup handles the remaining
    # session-related records.
    #

    delete_session(
        session_id
    )

def main():
    session_id = None
    try:
        session_id = create_session()
        print("RESEARCH GRAPH INTEGRATION")
        print("==========================")
        print(f"Disposable session: {session_id}")

        # Fixture initialization only: production lifecycle changes below
        # are performed exclusively through fenced repository methods.
        set_session_status(session_id, "created")
        assert get_status(session_id) == "created"

        lease = acquire_lease(session_id)
        prepare_session(session_id, lease)
        assert get_status(session_id) == "planning"
        print("TEST 1 - Execution prepared: PASSED")

        fake_model = FakeStructuredChatModel()
        fake_search = FakeSearchProvider()
        fake_retriever = FakeDocumentRetriever()

        models = SimpleNamespace(
            planner=fake_model,
            researcher=fake_model,
            summariser=fake_model,
            reviewer=fake_model,
            reporter=fake_model,
            controller=fake_model,
        )

        graph = create_research_graph(
            models=models,
            session_factory=SessionLocal,
            search_provider=fake_search,
            document_retriever=fake_retriever,
            document_extractor=HtmlDocumentExtractor(),
        )

        initial_state = {
            "session_id": session_id,
            "topic": "Deterministic graph integration test",
            "scope": None,
            "resume": False,
            "resume_phase": None,
            "execution_target": "research",
            "pause_requested": False,
            "research_plan": None,
            "current_question_id": None,
            "current_question": None,
            "search_required": True,
            "current_search_attempt_id": None,
            "search_plan": None,
            "search_results": [],
            "current_review_question_id": None,
            "current_review_question": None,
        }

        result = graph.invoke(
            initial_state,
            config={
                "configurable": {"execution_lease": lease},
                "recursion_limit": 100,
            },
        )
        assert isinstance(result, dict)
        print("TEST 2 - Production graph returned: PASSED")

        assert get_status(session_id) == "researched", (
            f"Unexpected research session status: {get_status(session_id)}"
        )
        print("TEST 3 - Research lifecycle completed: PASSED")

        assert fake_model.calls["ResearchPlan"] == 1, fake_model.calls
        assert fake_model.calls["SearchPlan"] == 1, fake_model.calls
        assert fake_model.calls["SourceAnalysis"] == 1, fake_model.calls
        assert sum(fake_model.calls.values()) == 3, fake_model.calls
        print("TEST 4 - Exactly three research model calls: PASSED")

        assert len(fake_search.calls) == 1, fake_search.calls
        assert fake_retriever.calls == [TEST_URL], fake_retriever.calls
        print("TEST 5 - Exactly one search and retrieval: PASSED")

        # These tables are used by the existing SQL Server persistence layer.
        # If your schema uses different names, adjust the names below only.
        expected_tables = {
            "research_questions": 1,
            "search_attempts": 1,
            "web_search_results": 1,
            "sources": 1,
            "findings": 1,
        }
        for table_name, minimum_count in expected_tables.items():
            count = count_rows_for_session(table_name, session_id)
            assert count >= minimum_count, (
                f"Expected at least {minimum_count} row(s) in "
                f"{table_name}, found {count}."
            )
            print(f"TEST - {table_name}: {count} persisted row(s): PASSED")

        print("\nPASS")

    finally:

        if session_id is not None:

            cleanup_graph_test_session(
                session_id
            )


if __name__ == "__main__":
    main()
