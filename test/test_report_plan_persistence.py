
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, select

from domain.report_plan import (
    ReportPlan,
    PlannedReportSection,
)

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import (
    QuestionReview,
    ReportPlanEntity,
    ReportPlannedSectionEntity,
    ReportPlannedSectionClaim,
    ResearchQuestion,
    ResearchSession,
    ReviewedClaimEntity,
)

from persistence.report_plan_repository import (
    ReportPlanRepository,
)

from persistence.models import (
    ReportGeneratedSectionEntity,
    ReportGeneratedSectionClaim,
)

from persistence.models import (
    ReportSynthesisEntity,
    ReportSynthesisLimitation,
)


def create_test_session(
    db,
) -> tuple[str, list[int]]:

    now = datetime.now(
        timezone.utc
    )

    session_id = str(
        uuid4()
    )

    research_session = ResearchSession(
        id=session_id,
        topic="Report plan persistence integration test",
        scope=None,
        status="reporting",
        pause_requested=False,
        execution_owner=None,
        execution_lease_expires_at=None,
        execution_lease_version=0,
        created_at=now,
        updated_at=now,
    )

    db.add(
        research_session
    )

    db.flush()

    question = ResearchQuestion(
        research_session_id=session_id,
        category="test",
        question="What evidence is available?",
        rationale="Test reviewed-claim ownership.",
        status="reviewed",
        created_at=now,
        updated_at=now,
    )

    db.add(
        question
    )

    db.flush()

    review = QuestionReview(
        research_question_id=question.id,
        answer="Test evidence has been reviewed.",
        overall_confidence="high",
        sufficient_evidence=True,
        created_at=now,
    )

    db.add(
        review
    )

    db.flush()

    claim_ids = []

    for index in range(
        1,
        4,
    ):

        claim = ReviewedClaimEntity(
            question_review_id=review.id,
            claim=f"Reviewed test claim {index}.",
            confidence="high",
        )

        db.add(
            claim
        )

        db.flush()

        claim_ids.append(
            claim.id
        )

    db.commit()

    return session_id, claim_ids


def build_test_plan(
    claim_ids: list[int],
) -> ReportPlan:

    return ReportPlan(
        title="Test Research Report",
        target_word_count=1000,
        executive_summary_word_count=50,
        conclusions_word_count=50,
        limitations_word_count=30,
        sections=[
            PlannedReportSection(
                ordinal=1,
                heading="First Test Section",
                purpose="Examine the first reviewed claim.",
                target_word_count=435,
                reviewed_claim_ids=[
                    claim_ids[0],
                ],
            ),
            PlannedReportSection(
                ordinal=2,
                heading="Second Test Section",
                purpose="Examine the remaining reviewed claims.",
                target_word_count=435,
                reviewed_claim_ids=[
                    claim_ids[1],
                    claim_ids[2],
                ],
            ),
        ],
    )


def delete_test_session(
    db,
    session_id: str,
) -> None:

    plan_entity = db.execute(
        select(
            ReportPlanEntity
        )
        .where(
            ReportPlanEntity.research_session_id
            == session_id
        )
    ).scalar_one_or_none()

    if plan_entity is not None:

        section_ids = db.execute(
            select(
                ReportPlannedSectionEntity.id
            )
            .where(
                ReportPlannedSectionEntity.report_plan_id
                == plan_entity.id
            )
        ).scalars().all()

        if section_ids:

            generated_section_ids = db.execute(
                select(
                    ReportGeneratedSectionEntity.id
                )
                .where(
                    ReportGeneratedSectionEntity.report_planned_section_id.in_(
                        section_ids
                    )
                )
            ).scalars().all()

            if generated_section_ids:

                db.execute(
                    delete(
                        ReportGeneratedSectionClaim
                    )
                    .where(
                        ReportGeneratedSectionClaim.report_generated_section_id.in_(
                            generated_section_ids
                        )
                    )
                )

            db.execute(
                delete(
                    ReportGeneratedSectionEntity
                )
                .where(
                    ReportGeneratedSectionEntity.report_planned_section_id.in_(
                        section_ids
                    )
                )
            )

        if section_ids:

            db.execute(
                delete(
                    ReportPlannedSectionClaim
                )
                .where(
                    ReportPlannedSectionClaim.report_planned_section_id.in_(
                        section_ids
                    )
                )
            )

        db.execute(
            delete(
                ReportPlannedSectionEntity
            )
            .where(
                ReportPlannedSectionEntity.report_plan_id
                == plan_entity.id
            )
        )

        synthesis_ids = db.execute(
            select(
                ReportSynthesisEntity.id
            )
            .where(
                ReportSynthesisEntity.report_plan_id
                == plan_entity.id
            )
        ).scalars().all()

        if synthesis_ids:

            db.execute(
                delete(
                    ReportSynthesisLimitation
                )
                .where(
                    ReportSynthesisLimitation.report_synthesis_id.in_(
                        synthesis_ids
                    )
                )
            )

            db.execute(
                delete(
                    ReportSynthesisEntity
                )
                .where(
                    ReportSynthesisEntity.id.in_(
                        synthesis_ids
                    )
                )
            )

        db.execute(
            delete(
                ReportPlanEntity
            )
            .where(
                ReportPlanEntity.id
                == plan_entity.id
            )
        )

    question_ids = db.execute(
        select(
            ResearchQuestion.id
        )
        .where(
            ResearchQuestion.research_session_id
            == session_id
        )
    ).scalars().all()

    if question_ids:

        review_ids = db.execute(
            select(
                QuestionReview.id
            )
            .where(
                QuestionReview.research_question_id.in_(
                    question_ids
                )
            )
        ).scalars().all()

        if review_ids:

            db.execute(
                delete(
                    ReviewedClaimEntity
                )
                .where(
                    ReviewedClaimEntity.question_review_id.in_(
                        review_ids
                    )
                )
            )

            db.execute(
                delete(
                    QuestionReview
                )
                .where(
                    QuestionReview.id.in_(
                        review_ids
                    )
                )
            )

        db.execute(
            delete(
                ResearchQuestion
            )
            .where(
                ResearchQuestion.id.in_(
                    question_ids
                )
            )
        )

    db.execute(
        delete(
            ResearchSession
        )
        .where(
            ResearchSession.id
            == session_id
        )
    )

    db.commit()


def main():

    session_id = None

    with SessionLocal() as db:

        try:

            session_id, claim_ids = (
                create_test_session(
                    db
                )
            )

            print()
            print(
                "REPORT PLAN PERSISTENCE TEST"
            )

            print()
            print(
                f"Test session: {session_id}"
            )

            lease_repository = (
                ExecutionLeaseRepository(
                    db
                )
            )

            plan_repository = (
                ReportPlanRepository(
                    db
                )
            )

            lease = lease_repository.acquire(
                session_id
            )

            plan = build_test_plan(
                claim_ids
            )

            plan_repository.save_plan_fenced(
                session_id=session_id,
                plan=plan,
                lease=lease,
            )

            print(
                "Initial plan persistence: PASSED"
            )

            persisted_plan = (
                plan_repository.get_for_session(
                    session_id
                )
            )

            if persisted_plan is None:

                raise AssertionError(
                    "Persisted report plan was not found."
                )

            if not plan_repository._plans_match(
                existing=persisted_plan,
                requested=plan,
            ):

                raise AssertionError(
                    "Persisted report plan differs "
                    "from the requested plan."
                )

            print(
                "Plan reload and comparison: PASSED"
            )

            plan_repository.save_plan_fenced(
                session_id=session_id,
                plan=plan,
                lease=lease,
            )

            print(
                "Identical plan retry: PASSED"
            )

            changed_plan = deepcopy(
                plan
            )

            changed_plan.title = (
                "Modified Test Research Report"
            )

            try:

                plan_repository.save_plan_fenced(
                    session_id=session_id,
                    plan=changed_plan,
                    lease=lease,
                )

            except ValueError:

                print(
                    "Modified plan rejection: PASSED"
                )

            else:

                raise AssertionError(
                    "Modified report plan was accepted."
                )

            released = lease_repository.release(
                lease
            )

            if not released:

                raise AssertionError(
                    "Execution lease could not be released."
                )

            print(
                "Execution lease release: PASSED"
            )

            try:

                plan_repository.save_plan_fenced(
                    session_id=session_id,
                    plan=plan,
                    lease=lease,
                )

            except ExecutionLeaseFenceRejected:

                print(
                    "Released lease fencing: PASSED"
                )

            else:

                raise AssertionError(
                    "A released execution lease "
                    "was incorrectly accepted."
                )

            print()
            print(
                "All report plan persistence tests: PASSED"
            )

        finally:

            db.rollback()

            if session_id is not None:

                delete_test_session(
                    db=db,
                    session_id=session_id,
                )

                print(
                    "Test session cleanup: COMPLETED"
                )


if __name__ == "__main__":

    main()
