from collections import Counter
from types import SimpleNamespace

from langchain_core.runnables import RunnableLambda

from domain.report import ResearchReport
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


class ReportModel(ReviewModel):

    def __init__(
        self,
    ):

        super().__init__()

        self.reviewed_claim_id = None

    def with_structured_output(
        self,
        schema,
        **kwargs,
    ):

        if schema.__name__ != "ResearchReport":

            return super().with_structured_output(
                schema,
                **kwargs,
            )

        def respond(messages):

            self.calls["ResearchReport"] += 1

            assert self.reviewed_claim_id is not None

            report = ResearchReport(
                title="Controlled Research Report",
                executive_summary=(
                    "The reviewed evidence supports "
                    "the controlled test conclusion."
                ),
                sections=[
                    {
                        "heading": "Reviewed evidence",
                        "content": (
                            "The deterministic evidence "
                            "supports the controlled claim."
                        ),
                        "reviewed_claim_ids": [
                            self.reviewed_claim_id
                        ],
                    },
                ],
                conclusions=(
                    "The controlled evidence is sufficient "
                    "for this integration test."
                ),
                limitations=[
                    "The evidence is a deterministic fixture."
                ],
            )

            return report

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


def cleanup_report(
    session_id,
):

    with SessionLocal() as db:

        reports = (
            db.query(
                ResearchReportEntity
            )
            .filter(
                ResearchReportEntity.research_session_id
                == session_id
            )
            .all()
        )

        for report in reports:

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

            for section in sections:

                (
                    db.query(
                        ReportSectionClaim
                    )
                    .filter(
                        ReportSectionClaim.report_section_id
                        == section.id
                    )
                    .delete(
                        synchronize_session=False
                    )
                )

            (
                db.query(
                    ReportSectionEntity
                )
                .filter(
                    ReportSectionEntity.research_report_id
                    == report.id
                )
                .delete(
                    synchronize_session=False
                )
            )

            (
                db.query(
                    ReportLimitation
                )
                .filter(
                    ReportLimitation.research_report_id
                    == report.id
                )
                .delete(
                    synchronize_session=False
                )
            )

            db.delete(
                report
            )

        db.commit()


def main():

    session_id = None

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

        assert model.calls["ResearchReport"] == 1

        assert model.calls["ResearchQuestionReview"] == (
            research_calls["ResearchQuestionReview"]
        )

        assert model.calls["SourceAnalysis"] == (
            research_calls["SourceAnalysis"]
        )

        assert model.calls["ResearchPlan"] == (
            research_calls["ResearchPlan"]
        )

        assert model.calls["SearchPlan"] == (
            research_calls["SearchPlan"]
        )

        assert len(search.calls) == search_count

        assert len(retriever.calls) == retrieval_count

        print("TEST 6 - No repeated research or review: PASSED")

        with SessionLocal() as db:

            persisted = (
                ReportRepository(db)
                .get_for_session(
                    session_id
                )
            )

        assert persisted is not None

        assert persisted.title == "Controlled Research Report"

        assert len(persisted.sections) == 1

        assert persisted.sections[0].reviewed_claim_ids == [
            model.reviewed_claim_id
        ]

        assert persisted.limitations == [
            "The evidence is a deterministic fixture."
        ]

        print("TEST 7 - Report content and provenance persisted: PASSED")

        with SessionLocal() as db:

            report_count = (
                db.query(
                    ResearchReportEntity
                )
                .filter(
                    ResearchReportEntity.research_session_id
                    == session_id
                )
                .count()
            )

        assert report_count == 1

        print("TEST 8 - Exactly one report persisted: PASSED")

        with SessionLocal() as db:

            report_repository = ReportRepository(
                db
            )

            persisted_again = (
                report_repository.get_for_session(
                    session_id
                )
            )

        assert persisted_again is not None

        assert persisted_again.id == persisted.id

        assert status(session_id) == "completed"

        assert model.calls["ResearchReport"] == 1

        with SessionLocal() as db:

            report_count = (
                db.query(
                    ResearchReportEntity
                )
                .filter(
                    ResearchReportEntity.research_session_id
                    == session_id
                )
                .count()
            )

        assert report_count == 1

        print(
            "TEST 9 - Completed report remains "
            "durable and unique: PASSED"
        )

        print("TEST 9 - Completed-session resume is idempotent: PASSED")

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
