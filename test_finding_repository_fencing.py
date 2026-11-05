
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import event, select, update

from domain.finding import (
    ExtractedFinding,
    SourceAnalysis,
)

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.finding_repository import (
    FindingRepository,
)

from persistence.models import (
    Finding,
    ResearchQuestion,
    ResearchSession,
    Source,
    SourceSummary,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


def utc_now():

    return datetime.now(timezone.utc).replace(
        tzinfo=None
    )


def make_analysis():

    return SourceAnalysis(
        summary="A summary of the test source.",
        findings=[
            ExtractedFinding(
                claim="The first test claim.",
                evidence="Evidence for the first claim.",
                relevance="Relevant to the question.",
                confidence="high",
            ),
            ExtractedFinding(
                claim="The second test claim.",
                evidence="Evidence for the second claim.",
                relevance="Relevant to the question.",
                confidence="medium",
            ),
        ],
    )


def make_session():

    with SessionLocal() as db:

        record = ResearchSessionRepository(db).create(
            topic="Finding persistence test",
            scope=None,
        )

        return record.id


def make_question_and_source(session_id):

    now = utc_now()

    with SessionLocal() as db:

        question = ResearchQuestion(
            research_session_id=session_id,
            category="technical",
            question="What does the test source establish?",
            rationale="Verify transactional persistence.",
            status="pending",
            created_at=now,
            updated_at=now,
        )

        db.add(question)
        db.flush()

        question_id = question.id

        source = Source(
            research_session_id=session_id,
            research_question_id=question_id,
            requested_url="https://example.com/test",
            final_url="https://example.com/test",
            title="Test source",
            content_type="text/html",
            status_code=200,
            content_hash=uuid4().hex,
            raw_content="<p>Test content</p>",
            extracted_text="Test content",
            created_at=now,
        )

        db.add(source)
        db.flush()

        source_id = source.id

        db.commit()

        return question_id, source_id


def count_analysis(source_id):

    with SessionLocal() as db:

        summary_count = len(
            db.scalars(
                select(SourceSummary.id).where(
                    SourceSummary.source_id == source_id
                )
            ).all()
        )

        finding_count = len(
            db.scalars(
                select(Finding.id).where(
                    Finding.source_id == source_id
                )
            ).all()
        )

        return summary_count, finding_count


def expect_rejection(
    source_id,
    question_id,
    lease,
    exception_type,
):

    before = count_analysis(source_id)

    with SessionLocal() as db:

        try:

            FindingRepository(db).save_analysis(
                source_id=source_id,
                question_id=question_id,
                analysis=make_analysis(),
                lease=lease,
            )

        except exception_type:

            pass

        else:

            raise AssertionError(
                "Analysis was unexpectedly saved."
            )

    after = count_analysis(source_id)

    assert after == before, (
        f"Analysis records changed: {before} -> {after}"
    )


def delete_session(session_id):

    with SessionLocal() as db:

        source_ids = select(Source.id).where(
            Source.research_session_id == session_id
        )

        question_ids = select(ResearchQuestion.id).where(
            ResearchQuestion.research_session_id == session_id
        )

        db.query(Finding).filter(
            Finding.source_id.in_(source_ids)
        ).delete(synchronize_session=False)

        db.query(SourceSummary).filter(
            SourceSummary.source_id.in_(source_ids)
        ).delete(synchronize_session=False)

        db.query(Source).filter(
            Source.research_session_id == session_id
        ).delete(synchronize_session=False)

        db.query(ResearchQuestion).filter(
            ResearchQuestion.id.in_(question_ids)
        ).delete(synchronize_session=False)

        record = db.get(
            ResearchSession,
            session_id,
        )

        if record is not None:

            db.delete(record)

        db.commit()


def main():

    print()
    print("FINDING REPOSITORY FENCING")
    print("==========================")

    session_ids = []

    try:

        session_a = make_session()
        session_ids.append(session_a)

        session_b = make_session()
        session_ids.append(session_b)

        question_a, source_a = (
            make_question_and_source(session_a)
        )

        question_b, source_b = (
            make_question_and_source(session_b)
        )

        with SessionLocal() as db:

            lease_a = ExecutionLeaseRepository(db).acquire(
                session_a,
                duration_seconds=120,
            )

        with SessionLocal() as db:

            lease_b = ExecutionLeaseRepository(db).acquire(
                session_b,
                duration_seconds=120,
            )

        FindingRepositoryTest = FindingRepository

        with SessionLocal() as db:

            FindingRepositoryTest(db).save_analysis(
                source_id=source_a,
                question_id=question_a,
                analysis=make_analysis(),
                lease=lease_a,
            )

        assert count_analysis(source_a) == (1, 2)

        print(
            "TEST 1 - Valid analysis committed: PASSED"
        )

        wrong_owner = replace(
            lease_b,
            owner=str(uuid4()),
        )

        expect_rejection(
            source_b,
            question_b,
            wrong_owner,
            ExecutionLeaseFenceRejected,
        )

        assert count_analysis(source_b) == (0, 0)

        print(
            "TEST 2 - Incorrect owner rejected: PASSED"
        )

        with SessionLocal() as db:

            db.execute(
                update(ResearchSession)
                .where(ResearchSession.id == session_b)
                .values(
                    execution_lease_expires_at=(
                        datetime(2000, 1, 1)
                    )
                )
            )

            db.commit()

        expect_rejection(
            source_b,
            question_b,
            lease_b,
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 3 - Expired lease rejected: PASSED"
        )

        with SessionLocal() as db:

            replacement_b = ExecutionLeaseRepository(
                db
            ).acquire(
                session_b,
                duration_seconds=120,
            )

        assert replacement_b.version > lease_b.version

        expect_rejection(
            source_b,
            question_b,
            lease_b,
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 4 - Superseded lease rejected: PASSED"
        )

        expect_rejection(
            source_b,
            question_b,
            lease_a,
            ValueError,
        )

        print(
            "TEST 5 - Cross-session source rejected: PASSED"
        )

        expect_rejection(
            source_b,
            question_b,
            lease_a,
            ValueError,
        )

        print(
            "TEST 5 - Cross-session source rejected: PASSED"
        )

        print(
            "TEST 6 - Cross-session question rejected: PASSED"
        )

        def fail_after_flush(
            db,
            flush_context,
        ):

            raise RuntimeError(
                "Simulated persistence failure"
            )

        with SessionLocal() as db:

            event.listen(
                db,
                "after_flush",
                fail_after_flush,
            )

            try:

                try:

                    FindingRepository(db).save_analysis(
                        source_id=source_b,
                        question_id=question_b,
                        analysis=make_analysis(),
                        lease=replacement_b,
                    )

                except RuntimeError as exc:

                    assert str(exc) == (
                        "Simulated persistence failure"
                    )

                else:

                    raise AssertionError(
                        "Expected persistence failure."
                    )

            finally:

                event.remove(
                    db,
                    "after_flush",
                    fail_after_flush,
                )

        assert count_analysis(source_b) == (0, 0)

        print(
            "TEST 7 - Failed transaction rolled back: PASSED"
        )

        with SessionLocal() as db:

            FindingRepository(db).save_analysis(
                source_id=source_b,
                question_id=question_b,
                analysis=make_analysis(),
                lease=replacement_b,
            )

        assert count_analysis(source_b) == (1, 2)

        print(
            "TEST 8 - Valid write after rollback: PASSED"
        )

        print()
        print("PASS")

    finally:

        for session_id in reversed(session_ids):

            delete_session(session_id)

            print(
                f"Disposable session removed: {session_id}"
            )


if __name__ == "__main__":

    main()
