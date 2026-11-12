from collections import Counter

from langchain_core.runnables import RunnableLambda

from application.research_workflow_service import ResearchWorkflowService
from persistence.database import SessionLocal
from persistence.report_repository import ReportRepository
from test_research_graph_pause_resume import set_pause
from test_research_graph_integration import (
    FakeSearchProvider,
    FakeDocumentRetriever,
    cleanup_graph_test_session,
)
from test_review_graph_integration import (
    cleanup_reviews,
    rows,
    status,
)
from test_report_graph_integration import (
    make_graph,
    cleanup_report,
)
from test_report_graph_pause_resume import report_counts
from test_workflow_controller_integration import (
    ControllerReportModel,
    assert_lease_released,
)


class ControllerPausingModel(ControllerReportModel):

    def __init__(
        self,
    ):

        super().__init__()

        self.pause_injected = False

    def with_structured_output(
        self,
        schema,
        **kwargs,
    ):

        runnable = super().with_structured_output(
            schema,
            **kwargs,
        )

        if schema.__name__ == "ResearchQuestionReview":

            def respond_review(
                messages,
            ):

                assert self.session_id is not None

                finding_rows = rows(
                    """
                    SELECT f.id
                    FROM dbo.findings f
                    JOIN dbo.research_questions q
                      ON q.id = f.research_question_id
                    WHERE q.research_session_id = :session_id
                    """,
                    session_id=self.session_id,
                )

                assert len(finding_rows) == 1

                self.finding_id = finding_rows[0].id

                return runnable.invoke(
                    messages
                )

            return RunnableLambda(
                respond_review
            )

        if schema.__name__ != "ResearchReport":

            return runnable

        def respond(
            messages,
        ):

            report = runnable.invoke(
                messages
            )

            if not self.pause_injected:

                assert self.session_id is not None

                set_pause(
                    self.session_id,
                    True,
                )

                self.pause_injected = True

                print(
                    "Injected cooperative pause during Report Agent invocation."
                )

            return report

        return RunnableLambda(
            respond
        )


class SessionBindingGraph:

    def __init__(
        self,
        graph,
        model,
    ):

        self.graph = graph
        self.model = model

    def invoke(
        self,
        initial_state,
        config=None,
    ):

        session_id = initial_state["session_id"]

        if self.model.session_id is None:

            self.model.session_id = session_id

        else:

            assert self.model.session_id == session_id

        return self.graph.invoke(
            initial_state,
            config=config,
        )


def main():

    session_id = None

    print("WORKFLOW CONTROLLER PAUSE / RESUME")
    print("==================================")

    try:

        model = ControllerPausingModel()

        search = FakeSearchProvider()

        retriever = FakeDocumentRetriever()

        graph = SessionBindingGraph(
            graph=make_graph(
                model,
                search,
                retriever,
            ),
            model=model,
        )

        service = ResearchWorkflowService(
            graph=graph,
            session_factory=SessionLocal,
            lease_duration_seconds=120,
            heartbeat_interval_seconds=30.0,
        )

        print("TEST 1 - Production controller prepared: PASSED")

        first_result = service.start(
            topic="Controlled controller cooperative pause and resume",
            scope="Deterministic evidence with durable pause",
        )

        session_id = first_result.session_id

        assert model.session_id == session_id

        assert model.pause_injected

        assert isinstance(first_result.graph_result, dict)

        assert first_result.graph_result.get("pause_requested") is True

        print("TEST 2 - Controller returned a cooperative pause: PASSED")

        assert status(session_id) == "reporting"

        print("TEST 3 - Paused session remains resumable: PASSED")

        assert_lease_released(
            session_id
        )

        print("TEST 4 - Paused execution lease released: PASSED")

        with SessionLocal() as db:

            report_before = ReportRepository(db).get_for_session(
                session_id
            )

        assert report_before is not None

        assert report_before.title == "Controlled Research Report"

        assert len(report_before.sections) == 1

        assert len(report_before.sections[0].reviewed_claim_ids) == 1

        original_report_id = report_before.id

        original_counts = report_counts(
            session_id
        )

        assert original_counts == {
            "reports": 1,
            "sections": 1,
            "references": 1,
            "limitations": 1,
        }

        print("TEST 5 - Report persisted before safe pause boundary: PASSED")

        original_calls = Counter(
            model.calls
        )

        original_search_count = len(
            search.calls
        )

        original_retrieval_count = len(
            retriever.calls
        )

        assert original_calls["ResearchQuestionReview"] == 1

        assert original_calls["ResearchReport"] == 1

        print("TEST 6 - Research, review and report each ran once: PASSED")

        set_pause(
            session_id,
            False,
        )

        print("TEST 7 - Durable pause request cleared: PASSED")

        resumed_result = service.resume(
            session_id
        )

        assert resumed_result.session_id == session_id

        assert status(session_id) == "completed"

        print("TEST 8 - Controller resumed to completion: PASSED")

        assert_lease_released(
            session_id
        )

        print("TEST 9 - Resumed execution lease released: PASSED")

        with SessionLocal() as db:

            report_after = ReportRepository(db).get_for_session(
                session_id
            )

        assert report_after is not None

        assert report_after.id == original_report_id

        assert report_counts(session_id) == original_counts

        assert report_after.sections[0].reviewed_claim_ids == [
            model.reviewed_claim_id
        ]

        print("TEST 10 - Persisted report and provenance unchanged: PASSED")

        assert Counter(model.calls) == original_calls

        assert len(search.calls) == original_search_count

        assert len(retriever.calls) == original_retrieval_count

        print("TEST 11 - No duplicate model or retrieval work: PASSED")

        try:

            service.resume(
                session_id
            )

        except ValueError as exc:

            assert "already been completed" in str(exc)

        else:

            raise AssertionError(
                "Completed workflow unexpectedly resumed."
            )

        print("TEST 12 - Completed session rejects resume: PASSED")

        print()
        print("PASS")

    finally:

        if session_id is None and "model" in locals():

            session_id = model.session_id

        if session_id is not None:

            try:

                set_pause(
                    session_id,
                    False,
                )

            finally:

                try:

                    cleanup_report(
                        session_id
                    )

                finally:

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
