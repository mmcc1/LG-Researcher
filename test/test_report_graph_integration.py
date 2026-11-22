from collections import Counter
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda

from domain.report import ReportSection

from domain.report_plan import (
    ProposedReportPlan,
    ProposedReportSection,
)

from domain.report_synthesis import (
    ReportSynthesis,
)
from extraction.html import HtmlDocumentExtractor
from graph.research_graph import create_research_graph
from persistence.database import SessionLocal
from persistence.report_repository import ReportRepository
from persistence.models import (
    ResearchReportEntity,
    ReportSectionEntity,
    ReportSectionClaim,
    ReportLimitation,
)
from test_search_result_fencing import (
    create_session,
    expire_lease,
)
from test_review_completion_fencing import acquire_lease
from test_review_selection_fencing import set_session_status
from test_research_graph_crash_recovery import prepare
from test_research_graph_integration import (
    FakeSearchProvider,
    FakeDocumentRetriever,
    cleanup_graph_test_session,
)
from test_review_graph_integration import (
    ReviewModel,
    cleanup_reviews,
    rows,
    status,
    invoke,
)

from application.report_file_writer import (
    ReportFileWriter,
)

from sqlalchemy import text

from persistence.report_plan_repository import (
    ReportPlanRepository,
)

from persistence.report_generated_section_repository import (
    ReportGeneratedSectionRepository,
)

from persistence.report_synthesis_repository import (
    ReportSynthesisRepository,
)

from unittest.mock import patch

from nodes.complete_report import (
    CompleteReportNode,
)

from pathlib import Path
from tempfile import TemporaryDirectory

class ReportModel(ReviewModel):

    SECTION_HEADINGS = (
        "Reviewed evidence",
        "Interpretation of evidence",
    )

    SECTION_CONTENT = (
        "The deterministic evidence supports "
        "the controlled claim.",

        "The reviewed claim establishes the presence "
        "of the controlled evidence marker.",
    )

    def __init__(
        self,
    ):

        super().__init__()

        self.reviewed_claim_id = None

        self.section_calls = Counter()


    def section_ordinal(
        self,
        messages,
    ):

        content = "\n".join(
            str(message.content)
            for message in messages
        )

        matches = [
            ordinal
            for ordinal in range(
                1,
                len(self.SECTION_HEADINGS) + 1,
            )
            if (
                f"SECTION ORDINAL:\n\n{ordinal}\n"
                in content
            )
        ]

        assert len(matches) == 1, (
            "Cannot identify the requested "
            f"report section: {matches}"
        )

        return matches[0]


    def with_structured_output(
        self,
        schema,
        **kwargs,
    ):

        name = schema.__name__

        if name not in {
            "ResearchReport",
            "ProposedReportPlan",
            "ReportSection",
            "ReportSynthesis",
        }:

            return super().with_structured_output(
                schema,
                **kwargs,
            )

        def respond(messages):

            self.calls[name] += 1

            if name == "ResearchReport":

                raise AssertionError(
                    "Unexpected legacy monolithic "
                    "report generation invocation."
                )

            assert self.reviewed_claim_id is not None

            if name == "ProposedReportPlan":

                return ProposedReportPlan(
                    title="Controlled Research Report",
                    sections=[
                        ProposedReportSection(
                            heading=self.SECTION_HEADINGS[0],
                            purpose=(
                                "Present the controlled "
                                "reviewed evidence."
                            ),
                            reviewed_claim_ids=[
                                self.reviewed_claim_id
                            ],
                        ),
                        ProposedReportSection(
                            heading=self.SECTION_HEADINGS[1],
                            purpose=(
                                "Interpret the significance "
                                "of the controlled evidence."
                            ),
                            reviewed_claim_ids=[
                                self.reviewed_claim_id
                            ],
                        ),
                    ],
                )

            if name == "ReportSection":

                ordinal = self.section_ordinal(
                    messages
                )

                self.section_calls[ordinal] += 1

                index = ordinal - 1

                return ReportSection(
                    heading=self.SECTION_HEADINGS[index],
                    content=self.SECTION_CONTENT[index],
                    reviewed_claim_ids=[
                        self.reviewed_claim_id
                    ],
                )

            if name == "ReportSynthesis":

                return ReportSynthesis(
                    executive_summary=(
                        "The reviewed evidence supports "
                        "the controlled test conclusion."
                    ),
                    conclusions=(
                        "The controlled evidence is sufficient "
                        "for this integration test."
                    ),
                    limitations=[
                        "The evidence is a deterministic fixture."
                    ],
                )

            raise AssertionError(
                f"Unexpected reporting schema: {name}"
            )

        return RunnableLambda(
            respond
        )


def make_graph(
    model,
    search,
    retriever,
    output_directory=None,
):

    models = SimpleNamespace(
        planner=model,
        researcher=model,
        summariser=model,
        reviewer=model,
        reporter=model,
        controller=model,
    )

    def build_graph():

        return create_research_graph(
            models=models,
            session_factory=SessionLocal,
            search_provider=search,
            document_retriever=retriever,
            document_extractor=HtmlDocumentExtractor(),
        )

    if output_directory is None:

        return build_graph()

    def create_test_complete_report(
        session_factory,
    ):

        node = CompleteReportNode(
            session_factory=session_factory
        )

        node.report_file_writer = ReportFileWriter(
            output_directory=output_directory
        )

        return node

    with patch(
        "graph.research_graph.CompleteReportNode",
        side_effect=create_test_complete_report,
    ):

        graph = build_graph()

    return graph


def acquire_replacement_lease(
    session_id,
):

    expire_lease(
        session_id
    )

    lease = acquire_lease(
        session_id
    )

    prepare(
        session_id,
        lease,
        resume=True,
    )

    return lease


def report_artifact_queries():

    report_ids = """
        SELECT id
        FROM dbo.research_reports
        WHERE research_session_id = :session_id
    """

    report_section_ids = f"""
        SELECT id
        FROM dbo.report_sections
        WHERE research_report_id IN ({report_ids})
    """

    plan_ids = """
        SELECT id
        FROM dbo.report_plans
        WHERE research_session_id = :session_id
    """

    planned_section_ids = f"""
        SELECT id
        FROM dbo.report_planned_sections
        WHERE report_plan_id IN ({plan_ids})
    """

    generated_section_ids = f"""
        SELECT id
        FROM dbo.report_generated_sections
        WHERE report_planned_section_id
            IN ({planned_section_ids})
    """

    synthesis_ids = f"""
        SELECT id
        FROM dbo.report_syntheses
        WHERE report_plan_id IN ({plan_ids})
    """

    return {
        "report_section_claims": f"""
            report_section_id IN ({report_section_ids})
        """,
        "report_limitations": f"""
            research_report_id IN ({report_ids})
        """,
        "report_sections": f"""
            research_report_id IN ({report_ids})
        """,
        "research_reports": """
            research_session_id = :session_id
        """,
        "report_synthesis_limitations": f"""
            report_synthesis_id IN ({synthesis_ids})
        """,
        "report_syntheses": f"""
            report_plan_id IN ({plan_ids})
        """,
        "report_generated_section_claims": f"""
            report_generated_section_id
                IN ({generated_section_ids})
        """,
        "report_generated_sections": f"""
            report_planned_section_id
                IN ({planned_section_ids})
        """,
        "report_planned_section_claims": f"""
            report_planned_section_id
                IN ({planned_section_ids})
        """,
        "report_planned_sections": f"""
            report_plan_id IN ({plan_ids})
        """,
        "report_plans": """
            research_session_id = :session_id
        """,
    }


def report_artifact_counts(
    session_id,
):

    counts = {}

    with SessionLocal() as db:

        for table, condition in (
            report_artifact_queries().items()
        ):

            count = db.execute(
                text(
                    f"""
                    SELECT COUNT(*)
                    FROM dbo.[{table}]
                    WHERE {condition}
                    """
                ),
                {
                    "session_id": session_id,
                },
            ).scalar_one()

            counts[table] = count

    return counts


def report_artifact_snapshot(
    session_id,
):

    snapshot = {}

    with SessionLocal() as db:

        for table, condition in (
            report_artifact_queries().items()
        ):

            result = db.execute(
                text(
                    f"""
                    SELECT *
                    FROM dbo.[{table}]
                    WHERE {condition}
                    """
                ),
                {
                    "session_id": session_id,
                },
            ).all()

            snapshot[table] = sorted(
                [
                    tuple(row)
                    for row in result
                ],
                key=repr,
            )

    return snapshot



def expected_report_artifact_counts():

    return {
        "report_section_claims": 2,
        "report_limitations": 1,
        "report_sections": 2,
        "research_reports": 1,
        "report_synthesis_limitations": 1,
        "report_syntheses": 1,
        "report_generated_section_claims": 2,
        "report_generated_sections": 2,
        "report_planned_section_claims": 2,
        "report_planned_sections": 2,
        "report_plans": 1,
    }


def expected_partial_report_artifact_counts():

    counts = {
        table: 0
        for table in expected_report_artifact_counts()
    }

    counts.update({
        "report_plans": 1,
        "report_planned_sections": 2,
        "report_planned_section_claims": 2,
        "report_generated_sections": 1,
        "report_generated_section_claims": 1,
    })

    return counts



def assert_report_artifacts_preserved(
    original_snapshot,
    current_snapshot,
):

    assert (
        original_snapshot.keys()
        == current_snapshot.keys()
    )

    for table, original_rows in (
        original_snapshot.items()
    ):

        current_rows = (
            current_snapshot[table]
        )

        for original_row in original_rows:

            assert original_row in current_rows, (
                "Previously persisted reporting "
                f"artifact changed or disappeared: "
                f"{table}: {original_row}"
            )


def expected_reporting_calls():

    return Counter({
        "ProposedReportPlan": 1,
        "ReportSection": 2,
        "ReportSynthesis": 1,
    })



def cleanup_report(
    session_id,
):

    with SessionLocal() as db:

        try:

            for table, condition in (
                report_artifact_queries().items()
            ):

                db.execute(
                    text(
                        f"""
                        DELETE FROM dbo.[{table}]
                        WHERE {condition}
                        """
                    ),
                    {
                        "session_id": session_id,
                    },
                )

            db.commit()

        except Exception:

            db.rollback()

            raise

    remaining_counts = report_artifact_counts(
        session_id
    )

    assert all(
        count == 0
        for count in remaining_counts.values()
    ), remaining_counts
    

def main():

    session_id = None

    temporary_directory = TemporaryDirectory(
        prefix="lgresearcher-report-test-"
    )

    output_directory = Path(
        temporary_directory.name
    )

    print("REPORT GRAPH INTEGRATION")
    print("========================")

    try:

        session_id = create_session()

        print(
            f"Disposable session: {session_id}"
        )

        set_session_status(
            session_id,
            "created",
        )

        model = ReportModel()

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

        model.finding_id = finding_rows[0].id

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

        reviewed_claim_rows = rows(
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

        assert len(reviewed_claim_rows) == 1

        model.reviewed_claim_id = (
            reviewed_claim_rows[0].id
        )

        print("TEST 3 - Review and provenance persisted: PASSED")

        research_calls = Counter(
            model.calls
        )

        search_count = len(
            search.calls
        )

        retrieval_count = len(
            retriever.calls
        )

        report_lease = acquire_replacement_lease(
            session_id
        )

        print("TEST 4 - Report worker prepared: PASSED")

        invoke(
            graph,
            session_id,
            report_lease,
            resume=True,
            target="complete",
        )

        assert status(session_id) == "completed"

        print("TEST 5 - Report graph completed: PASSED")

        expected_calls = research_calls + Counter({
            "ProposedReportPlan": 1,
            "ReportSection": 2,
            "ReportSynthesis": 1,
        })

        assert model.calls == expected_calls, (
            model.calls
        )

        assert model.section_calls == Counter({
            1: 1,
            2: 1,
        }), model.section_calls

        assert len(search.calls) == search_count

        assert len(retriever.calls) == retrieval_count

        print(
            "TEST 6 - Incremental reporting invoked "
            "without repeated research or review: PASSED"
        )

        with SessionLocal() as db:

            plan = ReportPlanRepository(
                db
            ).get_for_session(
                session_id
            )

            generated_sections = (
                ReportGeneratedSectionRepository(
                    db
                ).get_generated_sections(
                    session_id
                )
            )

            synthesis = ReportSynthesisRepository(
                db
            ).get_for_session(
                session_id
            )

            persisted = ReportRepository(
                db
            ).get_for_session(
                session_id
            )

        assert plan is not None

        assert plan.title == "Controlled Research Report"

        assert len(plan.sections) == 2

        assert [
            section.ordinal
            for section in plan.sections
        ] == [1, 2]

        assert [
            section.heading
            for section in plan.sections
        ] == list(
            model.SECTION_HEADINGS
        )

        allocated_words = (
            plan.executive_summary_word_count
            + plan.conclusions_word_count
            + plan.limitations_word_count
            + sum(
                section.target_word_count
                for section in plan.sections
            )
        )

        assert allocated_words == plan.target_word_count

        for section in plan.sections:

            assert section.reviewed_claim_ids == [
                model.reviewed_claim_id
            ]

        print(
            "TEST 7 - Report plan and word "
            "allocations persisted: PASSED"
        )

        assert len(generated_sections) == 2

        for index, section in enumerate(
            generated_sections
        ):

            assert section.ordinal == index + 1

            assert section.heading == (
                model.SECTION_HEADINGS[index]
            )

            assert section.content == (
                model.SECTION_CONTENT[index]
            )

            assert section.actual_word_count > 0

            assert section.reviewed_claim_ids == [
                model.reviewed_claim_id
            ]

        print(
            "TEST 8 - Generated sections "
            "and provenance persisted: PASSED"
        )

        assert synthesis is not None

        assert synthesis.executive_summary == (
            "The reviewed evidence supports "
            "the controlled test conclusion."
        )

        assert synthesis.conclusions == (
            "The controlled evidence is sufficient "
            "for this integration test."
        )

        assert synthesis.limitations == [
            "The evidence is a deterministic fixture."
        ]

        print(
            "TEST 9 - Report synthesis persisted: PASSED"
        )

        assert persisted is not None

        assert persisted.title == plan.title

        assert persisted.executive_summary == (
            synthesis.executive_summary
        )

        assert persisted.conclusions == (
            synthesis.conclusions
        )

        assert persisted.limitations == (
            synthesis.limitations
        )

        assert len(persisted.sections) == 2

        for final_section, generated_section in zip(
            persisted.sections,
            generated_sections,
        ):

            assert final_section.ordinal == (
                generated_section.ordinal
            )

            assert final_section.heading == (
                generated_section.heading
            )

            assert final_section.content == (
                generated_section.content
            )

            assert final_section.reviewed_claim_ids == (
                generated_section.reviewed_claim_ids
            )

        print(
            "TEST 10 - Final report assembled "
            "from persisted artifacts: PASSED"
        )

        artifact_counts = report_artifact_counts(
            session_id
        )

        assert artifact_counts == (
            expected_report_artifact_counts()
        ), artifact_counts

        print(
            "TEST 11 - All reporting artifacts "
            "persisted exactly once: PASSED"
        )

        snapshot = report_artifact_snapshot(
            session_id
        )

        calls_before = Counter(
            model.calls
        )

        section_calls_before = Counter(
            model.section_calls
        )

        search_calls_before = list(
            search.calls
        )

        retrieval_calls_before = list(
            retriever.calls
        )

        expire_lease(
            session_id
        )

        recovery_lease = acquire_lease(
            session_id
        )

        assert recovery_lease.version != (
            report_lease.version
        )

        try:

            prepare(
                session_id,
                recovery_lease,
                resume=True,
            )

        except ValueError as exc:

            assert (
                "This research session has already "
                "been completed."
                in str(exc)
            ), str(exc)

        else:

            raise AssertionError(
                "Execution preparation incorrectly "
                "accepted a completed research session."
            )

        assert status(session_id) == "completed"

        assert report_artifact_snapshot(
            session_id
        ) == snapshot

        assert model.calls == calls_before

        assert model.section_calls == (
            section_calls_before
        )

        print(
            "TEST 12 - Completed session execution "
            "preparation rejected: PASSED"
        )

        invoke(
            graph,
            session_id,
            recovery_lease,
            resume=True,
            target="complete",
        )

        assert status(session_id) == "completed"

        assert model.calls == calls_before

        assert model.section_calls == (
            section_calls_before
        )

        assert search.calls == search_calls_before

        assert retriever.calls == retrieval_calls_before

        assert report_artifact_snapshot(
            session_id
        ) == snapshot

        print(
            "TEST 13 - Completed session graph routing "
            "preserves every reporting artifact: PASSED"
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
