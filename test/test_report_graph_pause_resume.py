from collections import Counter

from langchain_core.runnables import RunnableLambda

from persistence.database import SessionLocal
from persistence.report_repository import ReportRepository
from persistence.models import (
    ResearchReportEntity,
    ReportSectionEntity,
    ReportSectionClaim,
    ReportLimitation,
)
from test_search_result_fencing import create_session
from test_review_selection_fencing import set_session_status
from test_research_graph_crash_recovery import prepare
from test_research_graph_pause_resume import set_pause
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
    expected_reporting_calls,
)

from pathlib import Path
from tempfile import TemporaryDirectory


class PausingReportModel(ReportModel):

    def __init__(
        self,
        session_id,
    ):

        super().__init__()

        self.session_id = session_id

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

        if schema.__name__ != "ReportSynthesis":

            return runnable

        def respond(
            messages,
        ):

            synthesis = runnable.invoke(
                messages
            )

            if not self.pause_injected:

                set_pause(
                    self.session_id,
                    True,
                )

                self.pause_injected = True

                print(
                    "Injected pause during "
                    "report synthesis invocation."
                )

            return synthesis

        return RunnableLambda(
            respond
        )


def report_counts(
    session_id,
):

    with SessionLocal() as db:

        report = (
            db.query(
                ResearchReportEntity
            )
            .filter(
                ResearchReportEntity.research_session_id
                == session_id
            )
            .first()
        )

        if report is None:

            return {
                "reports": 0,
                "sections": 0,
                "references": 0,
                "limitations": 0,
            }

        sections = (
            db.query(
                ReportSectionEntity
            )
            .filter(
                ReportSectionEntity.research_report_id
                == report.id
            )
            .all()
        )

        section_ids = [
            section.id
            for section in sections
        ]

        references = 0

        for section_id in section_ids:

            references += (
                db.query(
                    ReportSectionClaim
                )
                .filter(
                    ReportSectionClaim.report_section_id
                    == section_id
                )
                .count()
            )

        limitations = (
            db.query(
                ReportLimitation
            )
            .filter(
                ReportLimitation.research_report_id
                == report.id
            )
            .count()
        )

        return {
            "reports": 1,
            "sections": len(sections),
            "references": references,
            "limitations": limitations,
        }


def main():

    session_id = None

    print("REPORT GRAPH PAUSE / RESUME")
    print("===========================")

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

        model = PausingReportModel(
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

        assert len(finding_rows) == 1

        model.finding_id = (
            finding_rows[0].id
        )

        print("TEST 2 - Research completed: PASSED")

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

        claim_rows = rows(
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

        assert len(claim_rows) == 1

        model.reviewed_claim_id = (
            claim_rows[0].id
        )

        print("TEST 3 - Review completed: PASSED")

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

        paused_result = invoke(
            graph,
            session_id,
            report_lease,
            resume=True,
            target="complete",
        )

        assert isinstance(
            paused_result,
            dict,
        )

        assert paused_result.get(
            "pause_requested"
        ) is True

        assert model.pause_injected

        assert status(session_id) == "reporting"

        print(
            "TEST 5 - Pause honoured at report "
            "graph boundary: PASSED"
        )

        assert not report_path.exists(), (
            "Report was published despite "
            "the durable pause request."
        )

        print(
            "TEST 6 - Report publication "
            "prevented while paused: PASSED"
        )

        with SessionLocal() as db:

            original_report = (
                ReportRepository(db)
                .get_for_session(
                    session_id
                )
            )

        assert original_report is not None

        assert original_report.title == (
            "Controlled Research Report"
        )

        assert len(
            original_report.sections
        ) == 2

        for index, section in enumerate(
            original_report.sections
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

        assert original_report.limitations == [
            "The evidence is a deterministic fixture."
        ]

        print(
            "TEST 7 - Final report and provenance "
            "persisted before pause: PASSED"
        )

        paused_counts = report_artifact_counts(
            session_id
        )

        assert paused_counts == (
            expected_report_artifact_counts()
        ), paused_counts

        assert model.calls == (
            previous_calls
            + expected_reporting_calls()
        ), model.calls

        assert model.section_calls == Counter({
            1: 1,
            2: 1,
        }), model.section_calls

        paused_snapshot = report_artifact_snapshot(
            session_id
        )

        paused_model_calls = Counter(
            model.calls
        )

        paused_section_calls = Counter(
            model.section_calls
        )

        paused_search_calls = list(
            search.calls
        )

        paused_retrieval_calls = list(
            retriever.calls
        )

        print(
            "TEST 8 - All reporting artifacts "
            "durable before resume: PASSED"
        )

        set_pause(
            session_id,
            False,
        )

        replacement_lease = acquire_replacement_lease(
            session_id
        )

        assert replacement_lease.version != (
            report_lease.version
        )

        print(
            "TEST 9 - Replacement worker prepared: PASSED"
        )

        resumed_result = invoke(
            graph,
            session_id,
            replacement_lease,
            resume=True,
            target="complete",
        )

        assert isinstance(
            resumed_result,
            dict,
        )

        assert status(session_id) == "completed"

        print(
            "TEST 10 - Report recovery "
            "completed session: PASSED"
        )

        with SessionLocal() as db:

            final_report = (
                ReportRepository(db)
                .get_for_session(
                    session_id
                )
            )

        assert final_report is not None

        assert final_report.id == (
            original_report.id
        )

        assert len(
            final_report.sections
        ) == 2

        for original_section, final_section in zip(
            original_report.sections,
            final_report.sections,
        ):

            assert final_section.id == (
                original_section.id
            )

            assert final_section.heading == (
                original_section.heading
            )

            assert final_section.content == (
                original_section.content
            )

            assert final_section.reviewed_claim_ids == (
                original_section.reviewed_claim_ids
            )

        final_snapshot = report_artifact_snapshot(
            session_id
        )

        assert final_snapshot == paused_snapshot, (
            "Reporting artifacts changed "
            "during pause recovery."
        )

        final_counts = report_artifact_counts(
            session_id
        )

        assert final_counts == paused_counts

        print(
            "TEST 11 - Every original reporting "
            "artifact preserved unchanged: PASSED"
        )

        assert model.calls == paused_model_calls

        assert model.section_calls == (
            paused_section_calls
        )

        print(
            "TEST 12 - No model inference "
            "repeated after resume: PASSED"
        )

        assert search.calls == paused_search_calls

        assert retriever.calls == (
            paused_retrieval_calls
        )

        assert len(search.calls) == (
            previous_searches
        )

        assert len(retriever.calls) == (
            previous_retrievals
        )

        print(
            "TEST 13 - Research and document "
            "retrieval not repeated: PASSED"
        )

        assert report_path.is_file()

        report_text = report_path.read_text(
            encoding="utf-8"
        )

        assert final_report.title in report_text

        for section in final_report.sections:

            assert section.heading in report_text

            assert section.content in report_text

        assert "BIBLIOGRAPHY" in report_text

        assert not list(
            output_directory.glob("*.tmp")
        )

        print(
            "TEST 14 - Report publication "
            "completed after resume: PASSED"
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

            print(
                f"Disposable session removed: {session_id}"
            )


if __name__ == "__main__":

    main()
