
from dataclasses import replace
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import event, select

from domain.source import SourceDocument

from persistence.database import SessionLocal

from persistence.execution_lease_repository import (
    ExecutionLeaseFenceRejected,
    ExecutionLeaseRepository,
)

from persistence.models import (
    Source,
)

from persistence.source_repository import (
    SourceRepository,
)

from test_search_result_fencing import (
    create_session,
    create_question,
    delete_session,
    expire_lease,
)


def make_document(
    url: str,
    content: str = "Test source content.",
) -> SourceDocument:

    return SourceDocument(
        requested_url=url,
        final_url=url,
        title="Test Source",
        content_type="text/html",
        status_code=200,
        content_hash=sha256(
            content.encode("utf-8")
        ).hexdigest(),
        raw_content=content,
        extracted_text=content,
    )


def get_sources(
    session_id: str,
):

    with SessionLocal() as db:

        rows = db.execute(
            select(
                Source.id,
                Source.research_question_id,
                Source.requested_url,
                Source.content_hash,
                Source.raw_content,
            )
            .where(
                Source.research_session_id
                == session_id
            )
            .order_by(
                Source.id
            )
        ).all()

        return tuple(
            tuple(row)
            for row in rows
        )


def save_document(
    session_id,
    question_id,
    document,
    lease,
):

    with SessionLocal() as db:

        source = SourceRepository(
            db
        ).save(
            session_id=session_id,
            question_id=question_id,
            document=document,
            lease=lease,
        )

        return source.id


def expect_rejection(
    session_id,
    question_id,
    document,
    lease,
    exception_type,
):

    before = get_sources(
        session_id
    )

    try:

        save_document(
            session_id,
            question_id,
            document,
            lease,
        )

    except exception_type:

        pass

    else:

        raise AssertionError(
            "Source persistence was "
            "unexpectedly accepted."
        )

    assert get_sources(session_id) == before, (
        "Rejected source persistence "
        "changed the database."
    )


def main():

    print()
    print("SOURCE PERSISTENCE FENCING")
    print("==========================")

    session_a = create_session()
    session_b = create_session()

    try:

        question_a = create_question(
            session_a
        )

        question_b = create_question(
            session_b
        )

        with SessionLocal() as db:

            lease_a = ExecutionLeaseRepository(
                db
            ).acquire(
                session_a
            )

            lease_b = ExecutionLeaseRepository(
                db
            ).acquire(
                session_b
            )

        url_a = (
            "https://example.com/"
            f"source-{uuid4()}"
        )

        url_b = (
            "https://example.com/"
            f"source-{uuid4()}"
        )

        document_a = make_document(
            url_a
        )

        document_b = make_document(
            url_b
        )

        # Valid persistence.

        source_id = save_document(
            session_a,
            question_a,
            document_a,
            lease_a,
        )

        sources = get_sources(
            session_a
        )

        assert len(sources) == 1
        assert sources[0][0] == source_id

        print(
            "TEST 1 - Valid source committed: PASSED"
        )

        # Identical retry.

        before = get_sources(
            session_a
        )

        repeated_id = save_document(
            session_a,
            question_a,
            document_a,
            lease_a,
        )

        assert repeated_id == source_id

        assert get_sources(session_a) == before

        print(
            "TEST 2 - Duplicate URL unchanged: PASSED"
        )

        # Incorrect lease owner.

        invalid_lease = replace(
            lease_b,
            owner=str(uuid4()),
        )

        expect_rejection(
            session_b,
            question_b,
            document_b,
            invalid_lease,
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 3 - Incorrect owner rejected: PASSED"
        )

        # Expired lease.

        expire_lease(
            session_b
        )

        expect_rejection(
            session_b,
            question_b,
            document_b,
            lease_b,
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 4 - Expired lease rejected: PASSED"
        )

        # Superseded lease.

        with SessionLocal() as db:

            replacement_lease_b = (
                ExecutionLeaseRepository(db).acquire(
                    session_b
                )
            )

        expect_rejection(
            session_b,
            question_b,
            document_b,
            lease_b,
            ExecutionLeaseFenceRejected,
        )

        print(
            "TEST 5 - Superseded lease rejected: PASSED"
        )

        # Cross-session lease.

        expect_rejection(
            session_b,
            question_b,
            document_b,
            lease_a,
            ValueError,
        )

        print(
            "TEST 6 - Cross-session lease rejected: PASSED"
        )

        # Cross-session question.

        expect_rejection(
            session_b,
            question_a,
            document_b,
            replacement_lease_b,
            ValueError,
        )

        print(
            "TEST 7 - Cross-session question rejected: PASSED"
        )

        # Simulated failure after INSERT flush.

        before = get_sources(
            session_b
        )

        with SessionLocal() as db:

            def fail_after_flush(
                session,
                flush_context,
            ):

                raise RuntimeError(
                    "Simulated transaction failure."
                )

            event.listen(
                db,
                "after_flush",
                fail_after_flush,
            )

            try:

                try:

                    SourceRepository(
                        db
                    ).save(
                        session_id=session_b,
                        question_id=question_b,
                        document=document_b,
                        lease=replacement_lease_b,
                    )

                except RuntimeError as exc:

                    assert str(exc) == (
                        "Simulated transaction failure."
                    )

                else:

                    raise AssertionError(
                        "Expected transaction failure."
                    )

            finally:

                event.remove(
                    db,
                    "after_flush",
                    fail_after_flush,
                )

        assert get_sources(session_b) == before

        print(
            "TEST 8 - Failed transaction rolled back: PASSED"
        )

        # Recovery after rollback.

        recovered_id = save_document(
            session_b,
            question_b,
            document_b,
            replacement_lease_b,
        )

        assert recovered_id is not None

        assert len(
            get_sources(session_b)
        ) == 1

        print(
            "TEST 9 - Valid write after rollback: PASSED"
        )

        print()
        print("PASS")

    finally:

        # Source rows reference both the
        # research session and question.
        # Delete them before the shared
        # cleanup helpers run.

        with SessionLocal() as db:

            db.query(Source).filter(
                Source.research_session_id.in_(
                    [
                        session_a,
                        session_b,
                    ]
                )
            ).delete(
                synchronize_session=False
            )

            db.commit()

        delete_session(
            session_b
        )

        delete_session(
            session_a
        )


if __name__ == "__main__":

    main()
