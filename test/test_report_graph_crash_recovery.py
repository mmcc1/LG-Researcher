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
    report_artifact_counts,
    report_artifact_snapshot,
    expected_report_artifact_counts,
    expected_partial_report_artifact_counts,
    assert_report_artifacts_preserved,
    expected_reporting_calls,
)


from pathlib import Path
from tempfile import TemporaryDirectory


class InjectedReportCrash(RuntimeError):

    pass


class CrashOnceReportModel(ReportModel):

    def __init__(
        self,
    ):

        super().__init__()

        self.crash_enabled = True

        self.crash_count = 0

        self.section_attempts = Counter()


    def with_structured_output(
        self,
        schema,
        **kwargs,
    ):

        runnable = super().with_structured_output(
            schema,
            **kwargs,
        )

        if schema.__name__ != "ReportSection":

            return runnable

        def respond(
            messages,
        ):

            ordinal = self.section_ordinal(
                messages
            )

            self.section_attempts[ordinal] += 1

            if (
                ordinal == 2
                and self.crash_enabled
            ):

                self.crash_enabled = False

                self.crash_count += 1

                print(
                    "Injected worker crash during "
                    "second report section generation."
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

    temporary_directory = TemporaryDirectory(
        prefix="lgresearcher-report-test-"
    )

    output_directory = Path(
        temporary_directory.name
    )

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
            output_directory=output_directory,
        )

        report_path = (
            output_directory
            / f"{session_id}.txt"
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
            "Expected the injected failure "
            "to escape graph.invoke."
        )

        assert model.crash_count == 1

        assert model.section_attempts == Counter({
            1: 1,
            2: 1,
        }), model.section_attempts

        assert model.section_calls == Counter({
            1: 1,
        }), model.section_calls

        assert model.calls == (
            previous_calls + Counter({
                "ProposedReportPlan": 1,
                "ReportSection": 1,
            })
        ), model.calls

        print(
            "TEST 5 - Worker interrupted during "
            "second report section: PASSED"
        )

        assert status(session_id) == "reporting"

        assert not report_path.exists()

        with SessionLocal() as db:

            persisted = (
                ReportRepository(db)
                .get_for_session(
                    session_id
                )
            )

        assert persisted is None

        partial_counts = report_artifact_counts(
            session_id
        )

        assert partial_counts == (
            expected_partial_report_artifact_counts()
        ), partial_counts

        partial_snapshot = report_artifact_snapshot(
            session_id
        )

        print(
            "TEST 6 - Plan and first section durable; "
            "interrupted section absent: PASSED"
        )

        replacement_lease = acquire_replacement_lease(
            session_id
        )

        assert replacement_lease.version != (
            report_lease.version
        )

        print(
            "TEST 7 - Replacement worker prepared: PASSED"
        )

        invoke(
            graph,
            session_id,
            replacement_lease,
            resume=True,
            target="complete",
        )

        assert status(session_id) == "completed"

        assert model.crash_count == 1

        assert model.section_attempts == Counter({
            1: 1,
            2: 2,
        }), model.section_attempts

        assert model.section_calls == Counter({
            1: 1,
            2: 1,
        }), model.section_calls

        print(
            "TEST 8 - Only interrupted section "
            "regenerated: PASSED"
        )

        final_snapshot = report_artifact_snapshot(
            session_id
        )

        assert_report_artifacts_preserved(
            partial_snapshot,
            final_snapshot,
        )

        print(
            "TEST 9 - Original plan and first section "
            "preserved unchanged: PASSED"
        )

        with SessionLocal() as db:

            recovered_report = (
                ReportRepository(db)
                .get_for_session(
                    session_id
                )
            )

        assert recovered_report is not None

        assert recovered_report.title == (
            "Controlled Research Report"
        )

        assert len(recovered_report.sections) == 2

        for index, section in enumerate(
            recovered_report.sections
        ):

            assert section.ordinal == index + 1

            assert section.heading == (
                model.SECTION_HEADINGS[index]
            )

            assert section.content == (
                model.SECTION_CONTENT[index]
            )

            assert section.reviewed_claim_ids == [
                model.reviewed_claim_id
            ]

        assert recovered_report.limitations == [
            "The evidence is a deterministic fixture."
        ]

        print(
            "TEST 10 - Recovered report content "
            "and provenance valid: PASSED"
        )

        final_counts = report_artifact_counts(
            session_id
        )

        assert final_counts == (
            expected_report_artifact_counts()
        ), final_counts

        print(
            "TEST 11 - No duplicate reporting "
            "artifacts: PASSED"
        )

        assert model.calls == (
            previous_calls
            + expected_reporting_calls()
        ), model.calls

        assert len(search.calls) == (
            previous_searches
        )

        assert len(retriever.calls) == (
            previous_retrievals
        )

        print(
            "TEST 12 - Research, review and completed "
            "reporting work not repeated: PASSED"
        )

        assert report_path.is_file()

        report_text = report_path.read_text(
            encoding="utf-8"
        )

        assert recovered_report.title in report_text

        for section in recovered_report.sections:

            assert section.heading in report_text

            assert section.content in report_text

        assert "BIBLIOGRAPHY" in report_text

        assert not list(
            output_directory.glob("*.tmp")
        )

        print(
            "TEST 13 - Recovered report published "
            "successfully: PASSED"
        )

        print()
        print("PASS")

    finally:

        temporary_directory.cleanup()

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
