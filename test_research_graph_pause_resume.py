from collections import Counter
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda
from sqlalchemy import text

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

from test_search_result_fencing import create_session, expire_lease
from test_review_completion_fencing import acquire_lease
from test_review_selection_fencing import set_session_status
from test_research_graph_integration import cleanup_graph_test_session


TOPIC = "Deterministic graph pause and resume test"
QUESTIONS = (
    "What does controlled evidence establish for question one?",
    "What does controlled evidence establish for question two?",
)
QUERIES = (
    "controlled evidence question one",
    "controlled evidence question two",
)
URLS = (
    "https://example.org/graph-pause-one",
    "https://example.org/graph-pause-two",
)


def set_pause(session_id: str, requested: bool) -> None:
    """Simulate the external pause controller writing the durable flag."""
    with SessionLocal() as db:
        result = db.execute(
            text(
                "UPDATE dbo.research_sessions "
                "SET pause_requested = :requested "
                "WHERE id = :session_id"
            ),
            {"requested": requested, "session_id": session_id},
        )
        assert result.rowcount == 1, "Pause target session not found."
        db.commit()


def session_status(session_id: str) -> str:
    with SessionLocal() as db:
        session = ResearchSessionRepository(db).get(session_id)
        assert session is not None
        return session.status


def question_rows(session_id: str):
    with SessionLocal() as db:
        return db.execute(
            text(
                "SELECT id, question, status FROM dbo.research_questions "
                "WHERE research_session_id = :session_id ORDER BY id"
            ),
            {"session_id": session_id},
        ).all()


def count_rows(table: str, session_id: str) -> int:
    # Only the fixed table names used below are accepted.
    assert table in {"search_attempts", "web_search_results", "sources"}
    with SessionLocal() as db:
        return db.execute(
            text(
                f"SELECT COUNT(*) FROM dbo.[{table}] "
                "WHERE research_session_id = :session_id"
            ),
            {"session_id": session_id},
        ).scalar_one()


def count_findings(session_id: str) -> int:
    with SessionLocal() as db:
        return db.execute(
            text(
                "SELECT COUNT(*) FROM dbo.findings f "
                "JOIN dbo.research_questions q ON q.id = f.research_question_id "
                "WHERE q.research_session_id = :session_id"
            ),
            {"session_id": session_id},
        ).scalar_one()


class PauseAwareModel:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.calls = Counter()
        self.paused_once = False

    def with_structured_output(self, schema, **kwargs):
        name = schema.__name__

        def respond(messages):
            self.calls[name] += 1

            if name == "ResearchPlan":
                return ResearchPlan(
                    topic=TOPIC,
                    questions=[
                        ResearchQuestionPlan(
                            category="technical",
                            question=q,
                            rationale="Verify durable graph pause/resume.",
                        )
                        for q in QUESTIONS
                    ],
                )

            if name == "SearchPlan":
                content = "\n".join(str(m.content) for m in messages)
                matches = [i for i, q in enumerate(QUESTIONS) if q in content]
                assert len(matches) == 1, "Search plan question not identifiable."
                i = matches[0]
                return SearchPlan(
                    queries=[SearchQuery(query=QUERIES[i], rationale="Test evidence")]
                )

            if name == "SourceAnalysis":
                content = "\n".join(str(m.content) for m in messages)
                matches = [i for i, q in enumerate(QUESTIONS) if q in content]
                assert len(matches) == 1, "Source analysis question not identifiable."
                i = matches[0]

                # The first analysis has finished inference but has not yet
                # persisted. Request a durable pause; the graph must finish
                # this question before stopping at check_pause_research.
                if i == 0 and not self.paused_once:
                    set_pause(self.session_id, True)
                    self.paused_once = True

                return SourceAnalysis(
                    summary=f"Controlled source for question {i + 1}.",
                    findings=[
                        ExtractedFinding(
                            claim=f"Controlled evidence marker {i + 1} is present.",
                            evidence=f"The local document states marker {i + 1} is present.",
                            relevance="Directly addresses the selected question.",
                            confidence="high",
                        )
                    ],
                )

            raise AssertionError(f"Unexpected review/report model call: {name}")

        return RunnableLambda(respond)


class TwoQuestionSearch(SearchProvider):
    def __init__(self):
        self.calls = []

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        self.calls.append(query)
        assert query in QUERIES, f"Unexpected query: {query}"
        i = QUERIES.index(query)
        return [
            SearchResult(
                url=URLS[i],
                title=f"Controlled source {i + 1}",
                snippet=f"Controlled evidence marker {i + 1} is present.",
                rank=1,
                query=query,
                provider="integration-test",
            )
        ]


class TwoQuestionRetriever(DocumentRetriever):
    def __init__(self):
        self.calls = []

    def retrieve(self, url: str) -> RetrievedDocument:
        self.calls.append(url)
        assert url in URLS, f"Unexpected URL: {url}"
        i = URLS.index(url)
        html = (
            "<!doctype html><html><head>"
            f"<title>Controlled source {i + 1}</title>"
            "</head><body><article>"
            f"<h1>Controlled source {i + 1}</h1>"
            f"<p>Controlled evidence marker {i + 1} is present.</p>"
            "<p>This is local deterministic integration test evidence.</p>"
            "</article></body></html>"
        )
        return RetrievedDocument(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            content=html.encode("utf-8"),
        )


def initial_state(session_id: str, resume: bool) -> dict:
    return {
        "session_id": session_id,
        "topic": TOPIC,
        "scope": None,
        "resume": resume,
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


def invoke(graph, session_id, lease, resume):
    return graph.invoke(
        initial_state(session_id, resume),
        config={
            "configurable": {"execution_lease": lease},
            "recursion_limit": 100,
        },
    )


def main():
    session_id = None
    try:
        print("RESEARCH GRAPH PAUSE / RESUME")
        print("=============================")
        session_id = create_session()
        print(f"Disposable session: {session_id}")
        set_session_status(session_id, "created")

        first_lease = acquire_lease(session_id)
        with SessionLocal() as db:
            ResearchSessionRepository(db).prepare_execution_fenced(
                session_id=session_id,
                lease=first_lease,
                resume=False,
            )
        assert session_status(session_id) == "planning"
        print("TEST 1 - Execution prepared: PASSED")

        model = PauseAwareModel(session_id)
        search = TwoQuestionSearch()
        retriever = TwoQuestionRetriever()
        models = SimpleNamespace(
            planner=model,
            researcher=model,
            summariser=model,
            reviewer=model,
            reporter=model,
            controller=model,
        )
        graph = create_research_graph(
            models=models,
            session_factory=SessionLocal,
            search_provider=search,
            document_retriever=retriever,
            document_extractor=HtmlDocumentExtractor(),
        )

        first_result = invoke(graph, session_id, first_lease, resume=False)
        assert isinstance(first_result, dict)
        assert first_result.get("pause_requested") is True, first_result
        actual_status = session_status(session_id)

        print(
            "Session status after pause:",
            actual_status
        )

        rows = question_rows(session_id)

        print(
            "Question statuses after pause:",
            [
                (row.id, row.status)
                for row in rows
            ]
        )

        assert actual_status == "researching", (
            f"Expected researching, got {actual_status}"
        )
        rows = question_rows(session_id)
        assert len(rows) == 2, rows
        assert [row.status for row in rows] == ["researched", "pending"], rows
        print("TEST 2 - Graph paused after first completed question: PASSED")

        assert model.calls == Counter(
            {"ResearchPlan": 1, "SearchPlan": 1, "SourceAnalysis": 1}
        ), model.calls
        assert search.calls == [QUERIES[0]], search.calls
        assert retriever.calls == [URLS[0]], retriever.calls
        assert count_rows("search_attempts", session_id) == 1
        assert count_rows("web_search_results", session_id) == 1
        assert count_rows("sources", session_id) == 1
        assert count_findings(session_id) == 1
        print("TEST 3 - First question persisted exactly once: PASSED")

        # Simulate the controller releasing the pause, and replacement worker
        # acquiring a fresh lease after the original lease has expired.
        set_pause(session_id, False)
        expire_lease(
            first_lease.session_id
        )
        second_lease = acquire_lease(session_id)
        with SessionLocal() as db:
            ResearchSessionRepository(db).prepare_execution_fenced(
                session_id=session_id,
                lease=second_lease,
                resume=True,
            )
        assert session_status(session_id) == "researching"
        print("TEST 4 - Replacement lease prepared for resume: PASSED")

        second_result = invoke(graph, session_id, second_lease, resume=True)
        assert isinstance(second_result, dict)
        assert session_status(session_id) == "researched"
        assert [row.status for row in question_rows(session_id)] == [
            "researched", "researched"
        ]
        print("TEST 5 - Resume completed remaining question: PASSED")

        assert model.calls == Counter(
            {"ResearchPlan": 1, "SearchPlan": 2, "SourceAnalysis": 2}
        ), model.calls
        assert search.calls == list(QUERIES), search.calls
        assert retriever.calls == list(URLS), retriever.calls
        print("TEST 6 - Completed question not repeated: PASSED")

        assert count_rows("search_attempts", session_id) == 2
        assert count_rows("web_search_results", session_id) == 2
        assert count_rows("sources", session_id) == 2
        assert count_findings(session_id) == 2
        print("TEST 7 - All persisted records present without duplicates: PASSED")

        print("\nPASS")
    finally:
        if session_id is not None:
            cleanup_graph_test_session(session_id)


if __name__ == "__main__":
    main()
