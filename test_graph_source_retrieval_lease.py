
from dataclasses import replace
from uuid import uuid4

from langgraph.graph import (
    StateGraph,
    START,
    END,
)

from sqlalchemy import select

from domain.web import RetrievedDocument

from extraction.html import HtmlDocumentExtractor

from graph.state import ResearchState

from nodes.retrieve_sources import (
    RetrieveSourcesNode,
)

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import Source

from retrieval.base import DocumentRetriever

from test_search_result_fencing import (
    create_session,
    create_question,
    create_running_attempt,
    delete_session,
    get_snapshot,
    make_results,
    save_results,
)


class FakeRetriever(DocumentRetriever):

    def __init__(self):

        self.requested_urls = []

    def retrieve(
        self,
        url: str,
    ) -> RetrievedDocument:

        self.requested_urls.append(
            url
        )

        html = (
            "<html>"
            "<head>"
            "<title>Test Research Document</title>"
            "</head>"
            "<body>"
            "<h1>Research Evidence</h1>"
            "<p>Deterministic source content.</p>"
            "</body>"
            "</html>"
        )

        return RetrievedDocument(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            content=html.encode("utf-8"),
        )


class FailingRetriever(DocumentRetriever):

    def retrieve(
        self,
        url: str,
    ) -> RetrievedDocument:

        raise ConnectionError(
            "Simulated download failure."
        )


def create_graph(
    retriever: DocumentRetriever,
):

    builder = StateGraph(
        ResearchState
    )

    builder.add_node(
        "retrieve_sources",
        RetrieveSourcesNode(
            session_factory=SessionLocal,
            retriever=retriever,
            extractor=HtmlDocumentExtractor(),
            max_sources=5,
        ),
    )

    builder.add_edge(
        START,
        "retrieve_sources",
    )

    builder.add_edge(
        "retrieve_sources",
        END,
    )

    return builder.compile()


def make_state(
    session_id,
    question_id,
    attempt_id,
):

    return {
        "session_id": session_id,
        "current_question_id": question_id,
        "current_search_attempt_id": attempt_id,
    }


def invoke_graph(
    graph,
    state,
    lease=None,
):

    configurable = {}

    if lease is not None:

        configurable[
            "execution_lease"
        ] = lease

    return graph.invoke(
        state,
        config={
            "configurable": configurable,
        },
    )


def get_sources(
    session_id,
):

    with SessionLocal() as db:

        rows = db.execute(
            select(
                Source.id,
                Source.research_question_id,
                Source.requested_url,
                Source.title,
                Source.extracted_text,
                Source.content_hash,
            )
            .where(
                Source.research_session_id
                == session_id
            )
            .order_by(
                Source.id
            )
        ).all()

        return tuple(
            tuple(row)
            for row in rows
        )


def expect_rejection(
    graph,
    state,
    lease,
    exception_type,
):

    session_id = state[
        "session_id"
    ]

    before = get_sources(
        session_id
    )

    try:

        invoke_graph(
            graph,
            state,
            lease,
        )

    except exception_type:

        pass

    else:

        raise AssertionError(
            "Graph execution was "
            "unexpectedly accepted."
        )

    assert get_sources(session_id) == before, (
        "Rejected graph execution "
        "changed persisted sources."
    )


def cleanup_sources(
    session_ids,
):

    with SessionLocal() as db:

        db.query(Source).filter(
            Source.research_session_id.in_(
                session_ids
            )
        ).delete(
            synchronize_session=False
        )

        db.commit()


def main():

    print()
    print("GRAPH SOURCE RETRIEVAL LEASE")
    print("============================")

    session_a = create_session()
    session_b = create_session()

    try:

        question_a = create_question(
            session_a
        )

        question_b = create_question(
            session_b
        )

        attempt_a = create_running_attempt(
            session_a,
            question_a,
        )

        attempt_b = create_running_attempt(
            session_b,
            question_b,
        )

        with SessionLocal() as db:

            lease_a = ExecutionLeaseRepository(
                db
            ).acquire(
                session_a
            )

            lease_b = ExecutionLeaseRepository(
                db
            ).acquire(
                session_b
            )

        # Persist discovered search results
        # before exercising source retrieval.

        save_results(
            session_a,
            question_a,
            attempt_a,
            lease_a,
        )

        save_results(
            session_b,
            question_b,
            attempt_b,
            lease_b,
        )

        assert get_snapshot(attempt_a)[0] == "completed"
        assert get_snapshot(attempt_b)[0] == "completed"

        retriever = FakeRetriever()

        graph = create_graph(
            retriever
        )

        state_a = make_state(
            session_a,
            question_a,
            attempt_a,
        )

        state_b = make_state(
            session_b,
            question_b,
            attempt_b,
        )

        # Missing lease.

        expect_rejection(
            graph,
            state_a,
            None,
            RuntimeError,
        )

        assert not retriever.requested_urls

        print(
            "TEST 1 - Missing lease rejected: PASSED"
        )

        # Lease belongs to another session.

        expect_rejection(
            graph,
            state_b,
            lease_a,
            ValueError,
        )

        assert not retriever.requested_urls

        print(
            "TEST 2 - Mismatched lease rejected: PASSED"
        )

        # Invalid lease owner.
        # Retrieval may occur, but persistence
        # must fail at the execution fence.

        invalid_lease = replace(
            lease_a,
            owner=str(uuid4()),
        )

        expect_rejection(
            graph,
            state_a,
            invalid_lease,
            ExecutionLeaseFenceRejected,
        )

        assert retriever.requested_urls

        print(
            "TEST 3 - Invalid owner rejected: PASSED"
        )

        # A valid lease permits persistence.

        retriever.requested_urls.clear()

        invoke_graph(
            graph,
            state_a,
            lease_a,
        )

        sources = get_sources(
            session_a
        )

        assert len(sources) == len(
            make_results()
        )

        assert len(
            retriever.requested_urls
        ) == len(
            make_results()
        )

        assert all(
            source[3] == "Test Research Document"
            for source in sources
        )

        assert all(
            "Deterministic source content."
            in source[4]
            for source in sources
        )

        print(
            "TEST 4 - Valid graph persistence: PASSED"
        )

        # Retry must not insert duplicates
        # or download existing URLs again.

        before = get_sources(
            session_a
        )

        retriever.requested_urls.clear()

        invoke_graph(
            graph,
            state_a,
            lease_a,
        )

        assert get_sources(session_a) == before

        assert not retriever.requested_urls

        print(
            "TEST 5 - Graph retry idempotent: PASSED"
        )

        # Ensure the second session was
        # not modified.

        assert get_sources(
            session_b
        ) == ()

        print(
            "TEST 6 - Other session unchanged: PASSED"
        )

        # A normal download failure is recoverable
        # and should not create a source record.

        failing_graph = create_graph(
            FailingRetriever()
        )

        invoke_graph(
            failing_graph,
            state_b,
            lease_b,
        )

        assert get_sources(
            session_b
        ) == ()

        print(
            "TEST 7 - Download failure handled: PASSED"
        )

        # The second session can subsequently
        # retrieve sources successfully.

        invoke_graph(
            graph,
            state_b,
            lease_b,
        )

        assert len(
            get_sources(session_b)
        ) == len(
            make_results()
        )

        print(
            "TEST 8 - Recovery after download failure: PASSED"
        )

        print()
        print("PASS")

    finally:

        cleanup_sources(
            [
                session_a,
                session_b,
            ]
        )

        delete_session(
            session_b
        )

        delete_session(
            session_a
        )


if __name__ == "__main__":

    main()
