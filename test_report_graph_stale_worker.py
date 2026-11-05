from collections import Counter

from langchain_core.runnables import RunnableLambda

from persistence.database import SessionLocal
from persistence.report_repository import ReportRepository
from test_search_result_fencing import (
    create_session,
    expire_lease,
)
from test_review_selection_fencing import set_session_status
from test_research_graph_crash_recovery import prepare
from test_review_completion_fencing import acquire_lease
from test_review_graph_integration import (
    rows,
    status,
    invoke,
    cleanup_reviews,
)
from test_research_graph_integration import (
    FakeSearchProvider,
    FakeDocumentRetriever,
    cleanup_graph_test_session,
)
from test_report_graph_integration import (
    ReportModel,
    make_graph,
    acquire_replacement_lease,
    cleanup_report,
)
from test_report_graph_pause_resume import report_counts


class LeaseSupersedingReportModel(ReportModel):

    def __init__(
        self,
        session_id,
    ):

        super().__init__()

        self.session_id = session_id

        self.supersede_once = True

        self.old_lease = None

        self.replacement_lease = None

        self.report_attempts = 0

    def with_structured_output(
        self,
        schema,
        **kwargs,
    ):

        runnable = super().with_structured_output(
            schema,
            **kwargs,
        )

        if schema.__name__ != "ResearchReport":

            return runnable

        def respond(
            messages,
        ):

            self.report_attempts += 1

            result = runnable.invoke(
                messages
            )

            if self.supersede_once:

                self.supersede_once = False

                # Supersede execution ownership after inference,
                # before GenerateReportNode persists the report.

                expire_lease(
                    self.session_id
                )

                self.replacement_lease = acquire_lease(
                    self.session_id
                )

                assert self.old_lease is not None

                assert (
                    self.replacement_lease.version
                    != self.old_lease.version
                )

                print(
                    "Injected lease supersession during reporting: "
                    f"version {self.old_lease.version} -> "
                    f"{self.replacement_lease.version}"
                )

            return result

        return RunnableLambda(
            respond
        )


def main():

    session_id = None

    print("REPORT GRAPH STALE-WORKER FENCING")
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

        model = LeaseSupersedingReportModel(
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

        assert status(session_id) == "researched"

        findings = rows(
            """
            SELECT f.id
            FROM dbo.findings f
            JOIN dbo.research_questions q
              ON q.id = f.research_question_id
            WHERE q.research_session_id = :session_id
            """,
            session_id=session_id,
        )

        assert len(findings) == 1

        model.finding_id = findings[0].id

        print("TEST 2 - Research evidence persisted: PASSED")

        review_lease = acquire_replacement_lease(
            session_id
        )

        invoke(
            graph,
            session_id,
            review_lease,
            resume=True,
            target="review",
        )

        assert status(session_id) == "reviewed"

        claims = rows(
            """
            SELECT c.id
            FROM dbo.reviewed_claims c
            JOIN dbo.question_reviews qr
              ON qr.id = c.question_review_id
            JOIN dbo.research_questions q
              ON q.id = qr.research_question_id
            WHERE q.research_session_id = :session_id
            """,
            session_id=session_id,
        )

        assert len(claims) == 1

        model.reviewed_claim_id = claims[0].id

        print("TEST 3 - Review evidence persisted: PASSED")

        previous_calls = Counter(
            model.calls
        )

        previous_searches = len(
            search.calls
        )

        previous_retrievals = len(
            retriever.calls
        )

        report_lease = acquire_replacement_lease(
            session_id
        )

        model.old_lease = report_lease

        print("TEST 4 - Report worker prepared: PASSED")

        caught = None

        try:

            invoke(
                graph,
                session_id,
                report_lease,
                resume=True,
                target="complete",
            )

        except Exception as error:

            caught = error

            print(
                "Stale worker rejected: "
                f"{type(error).__name__}: {error}"
            )

        assert model.replacement_lease is not None, (
            "The Report Agent did not supersede the execution lease."
        )

        assert model.report_attempts == 1

        print("TEST 5 - Lease superseded during reporting: PASSED")

        assert caught is not None, (
            "The stale worker unexpectedly completed without rejection."
        )

        assert type(caught).__name__ == "ExecutionLeaseFenceRejected", (
            f"Unexpected exception type: {type(caught).__name__}"
        )

        print("TEST 6 - Stale worker rejected by lease fence: PASSED")

        assert status(session_id) == "reporting"

        with SessionLocal() as db:

            existing_report = (
                ReportRepository(db)
                .get_for_session(
                    session_id
                )
            )

        assert existing_report is None

        assert report_counts(
            session_id
        ) == {
            "reports": 0,
            "sections": 0,
            "references": 0,
            "limitations": 0,
        }

        print("TEST 7 - No partial report persistence: PASSED")

        replacement_lease = model.replacement_lease

        prepare(
            session_id,
            replacement_lease,
            resume=True,
        )

        print("TEST 8 - Replacement worker prepared: PASSED")

        invoke(
            graph,
            session_id,
            replacement_lease,
            resume=True,
            target="complete",
        )

        assert status(session_id) == "completed"

        assert model.report_attempts == 2

        assert model.calls["ResearchReport"] == 2

        print("TEST 9 - Replacement worker completed report: PASSED")

        with SessionLocal() as db:

            recovered_report = (
                ReportRepository(db)
                .get_for_session(
                    session_id
                )
            )

        assert recovered_report is not None

        assert recovered_report.title == "Controlled Research Report"

        assert len(recovered_report.sections) == 1

        assert recovered_report.sections[0].reviewed_claim_ids == [
            model.reviewed_claim_id
        ]

        assert recovered_report.limitations == [
            "The evidence is a deterministic fixture."
        ]

        print("TEST 10 - Recovered report provenance valid: PASSED")

        assert report_counts(
            session_id
        ) == {
            "reports": 1,
            "sections": 1,
            "references": 1,
            "limitations": 1,
        }

        print("TEST 11 - Exactly one complete report persisted: PASSED")

        for key, count in previous_calls.items():

            assert model.calls[key] == count

        assert len(search.calls) == previous_searches

        assert len(retriever.calls) == previous_retrievals

        print("TEST 12 - Research and review not repeated: PASSED")

        print()
        print("PASS")

    finally:

        if session_id is not None:

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
