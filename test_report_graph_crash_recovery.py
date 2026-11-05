from collections import Counter

from langchain_core.runnables import RunnableLambda

from persistence.database import SessionLocal
from persistence.report_repository import ReportRepository
from test_search_result_fencing import create_session
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


class InjectedReportCrash(RuntimeError):

    pass


class CrashOnceReportModel(ReportModel):

    def __init__(
        self,
    ):

        super().__init__()

        self.crash_enabled = True

        self.crash_count = 0

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

            if self.crash_enabled:

                self.crash_enabled = False

                self.crash_count += 1

                print(
                    "Injected worker crash during Report Agent invocation."
                )

                raise InjectedReportCrash(
                    "Simulated report worker crash"
                )

            return runnable.invoke(
                messages
            )

        return RunnableLambda(
            respond
        )


def main():

    session_id = None

    print("REPORT GRAPH CRASH RECOVERY")
    print("===========================")

    try:

        session_id = create_session()

        print(
            f"Disposable session: {session_id}"
        )

        set_session_status(
            session_id,
            "created",
        )

        model = CrashOnceReportModel()

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

        except InjectedReportCrash as error:

            caught = error

            print(
                f"Simulated worker interruption: {error}"
            )

        assert caught is not None, (
            "Expected the injected failure to escape graph.invoke."
        )

        assert model.crash_count == 1

        assert model.report_attempts == 1

        print("TEST 5 - Worker interrupted during reporting: PASSED")

        assert status(session_id) == "reporting"

        with SessionLocal() as db:

            persisted = (
                ReportRepository(db)
                .get_for_session(
                    session_id
                )
            )

        assert persisted is None

        assert report_counts(
            session_id
        ) == {
            "reports": 0,
            "sections": 0,
            "references": 0,
            "limitations": 0,
        }

        print("TEST 6 - No partial report persisted: PASSED")

        replacement_lease = acquire_replacement_lease(
            session_id
        )

        assert replacement_lease.version != report_lease.version

        print("TEST 7 - Replacement worker prepared: PASSED")

        invoke(
            graph,
            session_id,
            replacement_lease,
            resume=True,
            target="complete",
        )

        assert status(session_id) == "completed"

        assert model.report_attempts == 2

        assert model.calls["ResearchReport"] == 1

        print("TEST 8 - Report regenerated and session completed: PASSED")

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

        print("TEST 9 - Recovered report provenance valid: PASSED")

        assert report_counts(
            session_id
        ) == {
            "reports": 1,
            "sections": 1,
            "references": 1,
            "limitations": 1,
        }

        print("TEST 10 - No duplicate report records: PASSED")

        for key, count in previous_calls.items():

            assert model.calls[key] == count

        assert len(search.calls) == previous_searches

        assert len(retriever.calls) == previous_retrievals

        print("TEST 11 - Research and review not repeated: PASSED")

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
