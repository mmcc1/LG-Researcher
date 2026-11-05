from collections import Counter
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda

from extraction.html import HtmlDocumentExtractor
from graph.research_graph import create_research_graph
from persistence.database import SessionLocal
from test_search_result_fencing import create_session, expire_lease
from test_review_completion_fencing import acquire_lease
from test_review_selection_fencing import set_session_status
from test_research_graph_crash_recovery import prepare
from test_research_graph_pause_resume import (
    session_status,
    question_rows,
    count_rows,
    count_findings,
)
from test_review_graph_integration import (
    ReviewModel,
    cleanup_reviews,
    rows,
    invoke,
)
from test_review_graph_pause_resume import review_rows, support_rows
from test_research_graph_integration import (
    FakeSearchProvider,
    FakeDocumentRetriever,
    cleanup_graph_test_session,
)


class LeaseSupersedingReviewModel(ReviewModel):

    def __init__(
        self,
        session_id,
    ):

        super().__init__()

        self.session_id = session_id
        self.supersede_once = True
        self.old_lease = None
        self.replacement_lease = None

    def with_structured_output(
        self,
        schema,
        **kwargs,
    ):

        runnable = super().with_structured_output(
            schema,
            **kwargs,
        )

        if schema.__name__ != "ResearchQuestionReview":

            return runnable

        def respond(messages):

            result = runnable.invoke(
                messages
            )

            if self.supersede_once:

                self.supersede_once = False

                # Replace the lease after model inference but before
                # the original worker attempts to persist the review.

                expire_lease(
                    self.session_id
                )

                self.replacement_lease = acquire_lease(
                    self.session_id
                )

                assert (
                    self.replacement_lease.version
                    != self.old_lease.version
                )

                print(
                    "Injected lease supersession during review: "
                    f"version {self.old_lease.version} -> "
                    f"{self.replacement_lease.version}"
                )

            return result

        return RunnableLambda(
            respond
        )


def make_graph(
    model,
    search,
    retriever,
):

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

    return graph


def main():

    session_id = None

    print("REVIEW GRAPH STALE-WORKER FENCING")
    print("=================================")

    try:

        session_id = create_session()

        print(
            f"Disposable session: {session_id}"
        )

        set_session_status(
            session_id,
            "created",
        )

        model = LeaseSupersedingReviewModel(
            session_id
        )

        search = FakeSearchProvider()
        retriever = FakeDocumentRetriever()

        graph = make_graph(
            model,
            search,
            retriever,
        )

        research_lease = acquire_lease(
            session_id
        )

        prepare(
            session_id,
            research_lease,
            resume=False,
        )

        print("TEST 1 - Fixture prepared: PASSED")

        invoke(
            graph,
            session_id,
            research_lease,
            resume=False,
            target="research",
        )

        questions = question_rows(
            session_id
        )

        assert len(questions) == 1, questions
        assert session_status(session_id) == "researched"

        finding_rows = rows(
            """
            SELECT f.id
            FROM dbo.findings f
            JOIN dbo.research_questions q
              ON q.id = f.research_question_id
            WHERE q.research_session_id = :session_id
            """,
            session_id=session_id,
        )

        assert len(finding_rows) == 1, finding_rows

        model.finding_id = finding_rows[0].id

        print("TEST 2 - Research evidence persisted: PASSED")

        expire_lease(
            session_id
        )

        review_lease = acquire_lease(
            session_id
        )

        model.old_lease = review_lease

        prepare(
            session_id,
            review_lease,
            resume=True,
        )

        print("TEST 3 - Review worker prepared: PASSED")

        caught = None

        try:

            invoke(
                graph,
                session_id,
                review_lease,
                resume=True,
                target="review",
            )

        except Exception as exc:

            caught = exc

            print(
                "Stale worker rejected: "
                f"{type(exc).__name__}: {exc}"
            )

        assert model.replacement_lease is not None

        print("TEST 4 - Lease superseded during review: PASSED")

        assert caught is not None, (
            "The stale worker unexpectedly completed without rejection."
        )

        assert type(caught).__name__ == "ExecutionLeaseFenceRejected", (
            f"Unexpected exception type: {type(caught).__name__}"
        )

        print("TEST 5 - Stale worker rejected by lease fence: PASSED")

        assert session_status(session_id) == "reviewing"
        assert [q.status for q in question_rows(session_id)] == [
            "reviewing"
        ]
        assert len(review_rows(session_id)) == 0
        assert len(support_rows(session_id)) == 0

        print("TEST 6 - No partial review persistence: PASSED")

        replacement_lease = model.replacement_lease

        prepare(
            session_id,
            replacement_lease,
            resume=True,
        )

        print("TEST 7 - Replacement worker prepared: PASSED")

        invoke(
            graph,
            session_id,
            replacement_lease,
            resume=True,
            target="review",
        )

        assert session_status(session_id) == "reviewed"
        assert [q.status for q in question_rows(session_id)] == [
            "reviewed"
        ]

        print("TEST 8 - Replacement worker completed review: PASSED")

        completed_reviews = review_rows(
            session_id
        )

        assert len(completed_reviews) == 1, completed_reviews
        assert completed_reviews[0].research_question_id == questions[0].id

        references = [
            tuple(item)
            for item in support_rows(session_id)
        ]

        assert references == [
            (questions[0].id, model.finding_id)
        ], references

        assert count_rows("search_attempts", session_id) == 1
        assert count_rows("web_search_results", session_id) == 1
        assert count_rows("sources", session_id) == 1
        assert count_findings(session_id) == 1

        assert len(search.calls) == 1
        assert len(retriever.calls) == 1

        expected_calls = Counter({
            "ResearchPlan": 1,
            "SearchPlan": 1,
            "SourceAnalysis": 1,
            "ResearchQuestionReview": 2,
        })

        assert model.calls == expected_calls, model.calls

        print("TEST 9 - No duplicate persisted work: PASSED")
        print("\nPASS")

    finally:

        if session_id is not None:

            try:

                cleanup_reviews(
                    session_id
                )

            finally:

                cleanup_graph_test_session(
                    session_id
                )


if __name__ == "__main__":

    main()
