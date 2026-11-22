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
    report_artifact_counts,
    report_artifact_snapshot,
    expected_report_artifact_counts,
    expected_partial_report_artifact_counts,
    assert_report_artifacts_preserved,
    expected_reporting_calls,
)

from pathlib import Path
from tempfile import TemporaryDirectory


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

        self.section_attempts = Counter()

        self.before_supersession_snapshot = None


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

            result = runnable.invoke(
                messages
            )

            if (
                ordinal == 2
                and self.supersede_once
            ):

                self.supersede_once = False

                # Capture committed artifacts before
                # superseding execution ownership.

                self.before_supersession_snapshot = (
                    report_artifact_snapshot(
                        self.session_id
                    )
                )

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
                    "Injected lease supersession "
                    "after second section inference: "
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

        temporary_directory = TemporaryDirectory(
            prefix="lgresearcher-report-test-"
        )

        output_directory = Path(
            temporary_directory.name
        )

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
            "The second section invocation did not "
            "supersede the execution lease."
        )

        assert model.replacement_lease.version != (
            report_lease.version
        )

        assert model.section_attempts == Counter({
            1: 1,
            2: 1,
        }), model.section_attempts

        assert model.section_calls == Counter({
            1: 1,
            2: 1,
        }), model.section_calls

        assert model.calls == (
            previous_calls + Counter({
                "ProposedReportPlan": 1,
                "ReportSection": 2,
            })
        ), model.calls

        print(
            "TEST 5 - Lease superseded after "
            "second section inference: PASSED"
        )

        assert caught is not None, (
            "The stale worker unexpectedly "
            "completed without rejection."
        )

        assert type(caught).__name__ == (
            "ExecutionLeaseFenceRejected"
        ), (
            f"Unexpected exception type: "
            f"{type(caught).__name__}"
        )

        print(
            "TEST 6 - Stale worker rejected "
            "by lease fence: PASSED"
        )

        assert status(session_id) == "reporting"

        assert not report_path.exists()

        with SessionLocal() as db:

            existing_report = (
                ReportRepository(db)
                .get_for_session(
                    session_id
                )
            )

        assert existing_report is None

        partial_counts = report_artifact_counts(
            session_id
        )

        assert partial_counts == (
            expected_partial_report_artifact_counts()
        ), partial_counts

        print(
            "TEST 7 - Stale second section "
            "response not persisted: PASSED"
        )

        assert model.before_supersession_snapshot is not None

        partial_snapshot = report_artifact_snapshot(
            session_id
        )

        assert partial_snapshot == (
            model.before_supersession_snapshot
        ), (
            "Reporting artifacts changed "
            "after lease supersession."
        )

        print(
            "TEST 8 - Stale worker did not "
            "modify existing artifacts: PASSED"
        )

        replacement_lease = (
            model.replacement_lease
        )

        prepare(
            session_id,
            replacement_lease,
            resume=True,
        )

        print(
            "TEST 9 - Replacement worker "
            "prepared: PASSED"
        )

        invoke(
            graph,
            session_id,
            replacement_lease,
            resume=True,
            target="complete",
        )

        assert status(session_id) == "completed"

        assert model.section_attempts == Counter({
            1: 1,
            2: 2,
        }), model.section_attempts

        assert model.section_calls == Counter({
            1: 1,
            2: 2,
        }), model.section_calls

        print(
            "TEST 10 - Replacement worker regenerated "
            "only the rejected section: PASSED"
        )

        final_snapshot = report_artifact_snapshot(
            session_id
        )

        assert_report_artifacts_preserved(
            partial_snapshot,
            final_snapshot,
        )

        print(
            "TEST 11 - Original reporting artifacts "
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

        assert len(
            recovered_report.sections
        ) == 2

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
            "TEST 12 - Recovered report content "
            "and provenance valid: PASSED"
        )

        final_counts = report_artifact_counts(
            session_id
        )

        assert final_counts == (
            expected_report_artifact_counts()
        ), final_counts

        print(
            "TEST 13 - Exactly one complete set "
            "of reporting artifacts persisted: PASSED"
        )

        expected_calls = (
            previous_calls
            + expected_reporting_calls()
            + Counter({
                "ReportSection": 1,
            })
        )

        assert model.calls == (
            expected_calls
        ), model.calls

        assert len(search.calls) == (
            previous_searches
        )

        assert len(retriever.calls) == (
            previous_retrievals
        )

        print(
            "TEST 14 - Research, review and committed "
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
            "TEST 15 - Replacement worker published "
            "report successfully: PASSED"
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
