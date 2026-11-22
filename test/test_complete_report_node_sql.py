from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from application.report_file_writer import (
    ReportFileWriter,
)

from nodes.complete_report import (
    CompleteReportNode,
)

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseFenceRejected,
)

from persistence.models import (
    Source,
)

from test_search_result_fencing import (
    create_session,
    delete_session,
    expire_lease,
)

from test_review_selection_fencing import (
    create_review_question,
    set_session_status,
    get_snapshot as get_session_snapshot,
)

from test_review_persistence_fencing import (
    save_review,
    get_snapshot as get_question_snapshot,
)

from test_review_provenance_fencing import (
    create_source_and_findings,
    make_review,
    get_provenance_snapshot,
    delete_provenance,
)

from test_report_persistence_fencing import (
    make_report,
    persist_report,
    load_report,
    delete_report,
)

from test_report_citation_resolver_sql import (
    validate_database,
    get_reviewed_claim_ids,
    resolve_citations,
    assert_evidence_unchanged,
)


def acquire_lease(
    session_id,
):

    with SessionLocal() as db:

        lease = ExecutionLeaseRepository(
            db
        ).acquire(
            session_id,
            duration_seconds=300,
        )

    assert lease is not None

    return lease


def execute_node(
    node,
    session_id,
    lease,
    execution_guard=None,
):

    result = node(
        state={
            "session_id": session_id,
        },
        config={
            "configurable": {
                "execution_lease": lease,
                "execution_guard": execution_guard,
            },
        },
    )

    assert result == {}


def get_source_text(
    session_id,
    question_id,
    source_id,
):

    with SessionLocal() as db:

        source = db.get(
            Source,
            source_id,
        )

        assert source is not None

        assert (
            source.research_session_id
            == session_id
        )

        assert (
            source.research_question_id
            == question_id
        )

        return source.extracted_text


def set_source_text(
    session_id,
    question_id,
    source_id,
    extracted_text,
):

    with SessionLocal() as db:

        try:

            source = db.get(
                Source,
                source_id,
            )

            assert source is not None

            assert (
                source.research_session_id
                == session_id
            )

            assert (
                source.research_question_id
                == question_id
            )

            source.extracted_text = (
                extracted_text
            )

            db.commit()

        except Exception:

            db.rollback()

            raise


@contextmanager
def temporary_source_content(
    session_id,
    question_id,
    source_id,
    extracted_text,
):

    original_text = get_source_text(
        session_id=session_id,
        question_id=question_id,
        source_id=source_id,
    )

    try:

        set_source_text(
            session_id=session_id,
            question_id=question_id,
            source_id=source_id,
            extracted_text=extracted_text,
        )

        yield

    finally:

        set_source_text(
            session_id=session_id,
            question_id=question_id,
            source_id=source_id,
            extracted_text=original_text,
        )


def expect_invalid_evidence_rejected(
    node,
    session_id,
    question_id,
    source_id,
    extracted_text,
    lease,
    output_path,
):

    before_session = (
        get_session_snapshot(
            session_id
        )
    )

    before_report = load_report(
        session_id
    )

    before_provenance = (
        get_provenance_snapshot(
            question_id
        )
    )

    assert before_session[0] == "reporting"

    assert before_report is not None

    assert not output_path.exists()

    with temporary_source_content(
        session_id=session_id,
        question_id=question_id,
        source_id=source_id,
        extracted_text=extracted_text,
    ):

        try:

            execute_node(
                node=node,
                session_id=session_id,
                lease=lease,
            )

        except ValueError as exc:

            expected_message = (
                "a source containing no usable "
                f"research text: {source_id}"
            )

            assert expected_message in str(exc), (
                f"Unexpected rejection reason: {exc}"
            )

        else:

            raise AssertionError(
                "Contaminated report evidence "
                "was unexpectedly accepted."
            )

        assert (
            get_session_snapshot(session_id)
            == before_session
        )

        assert (
            load_report(session_id)
            == before_report
        )

        assert (
            get_provenance_snapshot(question_id)
            == before_provenance
        )

        assert not output_path.exists()

        assert not list(
            output_path.parent.glob("*.tmp")
        )


def expect_publication_failure(
    node,
    session_id,
    lease,
    output_path,
):

    before_session = (
        get_session_snapshot(
            session_id
        )
    )

    before_report = load_report(
        session_id
    )

    with patch(
        "application.report_file_writer.os.replace",
        side_effect=OSError(
            "Simulated report publication failure."
        ),
    ):

        try:

            execute_node(
                node=node,
                session_id=session_id,
                lease=lease,
            )

        except OSError as exc:

            assert (
                "Simulated report publication failure."
                in str(exc)
            )

        else:

            raise AssertionError(
                "Report publication failure "
                "was not propagated."
            )

    assert (
        get_session_snapshot(session_id)
        == before_session
    )

    assert (
        load_report(session_id)
        == before_report
    )

    assert not output_path.exists()

    assert not list(
        output_path.parent.glob("*.tmp")
    )


def expect_lease_expiry_after_publication(
    node,
    session_id,
    lease,
    output_path,
):

    before_report = load_report(
        session_id
    )

    guard_calls = []

    def execution_guard():

        guard_calls.append(
            len(guard_calls) + 1
        )

        if len(guard_calls) == 3:

            assert output_path.is_file()

            expire_lease(
                session_id
            )

    try:

        execute_node(
            node=node,
            session_id=session_id,
            lease=lease,
            execution_guard=execution_guard,
        )

    except ExecutionLeaseFenceRejected:

        pass

    else:

        raise AssertionError(
            "Report completion with an expired "
            "execution lease was accepted."
        )

    assert guard_calls == [
        1,
        2,
        3,
    ]

    assert (
        get_session_snapshot(session_id)[0]
        == "reporting"
    )

    assert (
        load_report(session_id)
        == before_report
    )

    assert output_path.is_file()

    report_text = output_path.read_text(
        encoding="utf-8"
    )

    assert "BIBLIOGRAPHY" in report_text

    assert "Sources cited: [1]" in report_text

    assert (
        "Contradicting evidence: [2]"
        in report_text
    )

    assert not list(
        output_path.parent.glob("*.tmp")
    )

    return output_path.read_bytes()


def expect_stale_completion_rejected(
    node,
    session_id,
    lease,
    output_path,
):

    before_session = (
        get_session_snapshot(
            session_id
        )
    )

    before_report = load_report(
        session_id
    )

    before_content = (
        output_path.read_bytes()
    )

    try:

        execute_node(
            node=node,
            session_id=session_id,
            lease=lease,
        )

    except ExecutionLeaseFenceRejected:

        pass

    else:

        raise AssertionError(
            "A superseded execution lease "
            "completed the research session."
        )

    assert (
        get_session_snapshot(session_id)
        == before_session
    )

    assert (
        load_report(session_id)
        == before_report
    )

    assert (
        output_path.read_bytes()
        == before_content
    )

    assert not list(
        output_path.parent.glob("*.tmp")
    )


def main():

    print()

    print(
        "COMPLETE REPORT NODE SQL INTEGRATION"
    )

    print(
        "===================================="
    )

    validate_database()

    sessions = []

    try:

        session_id = create_session()

        sessions.append(
            session_id
        )

        question_id = create_review_question(
            session_id,
            "reviewing",
        )

        supporting_source_id, supporting_ids = (
            create_source_and_findings(
                session_id=session_id,
                question_id=question_id,
                count=2,
            )
        )

        contradicting_source_id, contradicting_ids = (
            create_source_and_findings(
                session_id=session_id,
                question_id=question_id,
                count=1,
                title="",
            )
        )

        finding_ids = (
            supporting_ids
            + contradicting_ids
        )

        lease = acquire_lease(
            session_id
        )

        review = make_review(
            finding_ids
        )

        review_id = save_review(
            session_id,
            question_id,
            lease,
            review,
            set(finding_ids),
        )

        assert review_id is not None

        claim_ids = get_reviewed_claim_ids(
            review_id
        )

        assert len(claim_ids) == 2

        expected_provenance = (
            get_provenance_snapshot(
                question_id
            )
        )

        expected_question = (
            get_question_snapshot(
                question_id
            )
        )

        assert expected_question[0] == "reviewed"

        expected_citations = resolve_citations(
            session_id=session_id,
            claim_ids=claim_ids,
        )

        set_session_status(
            session_id,
            "reporting",
        )

        report = make_report(
            claim_ids
        )

        report.title = (
            "International research — Étude scientifique"
        )

        report.executive_summary = (
            "科学研究 — Δοκιμή"
        )

        report.sections[0].content = (
            "Research evidence: 研究、ข้อมูล、café、α + β."
        )

        report_id = persist_report(
            session_id,
            report,
            lease,
        )

        persisted_report = load_report(
            session_id
        )

        assert persisted_report is not None

        assert persisted_report.id == report_id

        assert (
            get_session_snapshot(session_id)[0]
            == "reporting"
        )

        print(
            "Disposable report fixture persisted."
        )

        with TemporaryDirectory() as directory:

            output_directory = Path(
                directory
            )

            output_path = (
                output_directory
                / f"{session_id}.txt"
            )

            node = CompleteReportNode(
                session_factory=SessionLocal,
            )

            node.report_file_writer = (
                ReportFileWriter(
                    output_directory=output_directory,
                )
            )

            def verify_original_evidence():

                assert_evidence_unchanged(
                    session_id=session_id,
                    question_id=question_id,
                    claim_ids=claim_ids,
                    expected_provenance=expected_provenance,
                    expected_snapshot=expected_question,
                    expected_citations=expected_citations,
                )

                assert (
                    load_report(session_id)
                    == persisted_report
                )

            expect_invalid_evidence_rejected(
                node=node,
                session_id=session_id,
                question_id=question_id,
                source_id=supporting_source_id,
                extracted_text="",
                lease=lease,
                output_path=output_path,
            )

            verify_original_evidence()

            print(
                "TEST 1 - Empty supporting source rejected: PASSED"
            )

            expect_invalid_evidence_rejected(
                node=node,
                session_id=session_id,
                question_id=question_id,
                source_id=contradicting_source_id,
                extracted_text="",
                lease=lease,
                output_path=output_path,
            )

            verify_original_evidence()

            print(
                "TEST 2 - Empty contradicting source rejected: PASSED"
            )

            expect_invalid_evidence_rejected(
                node=node,
                session_id=session_id,
                question_id=question_id,
                source_id=supporting_source_id,
                extracted_text="\t\r\n ",
                lease=lease,
                output_path=output_path,
            )

            verify_original_evidence()

            print(
                "TEST 3 - Whitespace supporting source rejected: PASSED"
            )

            expect_invalid_evidence_rejected(
                node=node,
                session_id=session_id,
                question_id=question_id,
                source_id=contradicting_source_id,
                extracted_text="\t\r\n ",
                lease=lease,
                output_path=output_path,
            )

            verify_original_evidence()

            print(
                "TEST 4 - Whitespace contradicting source rejected: PASSED"
            )

            assert not output_path.exists()

            verify_original_evidence()

            print(
                "TEST 5 - Original evidence restored: PASSED"
            )

            expect_publication_failure(
                node=node,
                session_id=session_id,
                lease=lease,
                output_path=output_path,
            )

            verify_original_evidence()

            print(
                "TEST 6 - Publication failure prevents completion: PASSED"
            )

            #
            # Expire the durable execution lease after
            # publication but before database completion.
            #

            published_content = (
                expect_lease_expiry_after_publication(
                    node=node,
                    session_id=session_id,
                    lease=lease,
                    output_path=output_path,
                )
            )

            verify_original_evidence()

            print(
                "TEST 7 - Expired lease after publication rejected: PASSED"
            )

            replacement_lease = acquire_lease(
                session_id
            )

            assert (
                replacement_lease.version
                > lease.version
            )

            execute_node(
                node=node,
                session_id=session_id,
                lease=replacement_lease,
            )

            assert (
                get_session_snapshot(session_id)[0]
                == "completed"
            )

            assert (
                output_path.read_bytes()
                == published_content
            )

            verify_original_evidence()

            print(
                "TEST 8 - Replacement worker completion: PASSED"
            )

            report_text = output_path.read_text(
                encoding="utf-8"
            )

            untitled_source = (
                expected_citations
                .claims[0]
                .contradicting_sources[0]
            )

            assert (
                untitled_source.source_id
                == contradicting_source_id
            )

            assert untitled_source.title == ""

            expected_bibliography_entry = (
                f"[2] {untitled_source.final_url}\n"
                f"{untitled_source.final_url}"
            )

            assert (
                expected_bibliography_entry
                in report_text
            )

            assert (
                report_text.count(
                    "Sources cited: [1]"
                ) == 2
            )

            assert (
                report_text.count(
                    "Contradicting evidence: [2]"
                ) == 2
            )

            print(
                "TEST 9 - Valid untitled source published: PASSED"
            )

            assert report.title in report_text

            assert (
                report.executive_summary
                in report_text
            )

            assert (
                report.sections[0].content
                in report_text
            )

            assert (
                output_path.read_bytes()
                == report_text.encode("utf-8")
            )

            print(
                "TEST 10 - Unicode publication preserved: PASSED"
            )

            completed_snapshot = (
                get_session_snapshot(
                    session_id
                )
            )

            execute_node(
                node=node,
                session_id=session_id,
                lease=replacement_lease,
            )

            assert (
                get_session_snapshot(session_id)
                == completed_snapshot
            )

            assert (
                output_path.read_bytes()
                == published_content
            )

            assert (
                load_report(session_id).id
                == report_id
            )

            assert list(
                output_directory.iterdir()
            ) == [
                output_path
            ]

            print(
                "TEST 11 - Idempotent completion: PASSED"
            )

            expect_stale_completion_rejected(
                node=node,
                session_id=session_id,
                lease=lease,
                output_path=output_path,
            )

            verify_original_evidence()

            print(
                "TEST 12 - Stale completion retry rejected: PASSED"
            )

            #
            # A report without reviewed claims must
            # remain publishable when no evidence exists.
            #

            empty_session_id = create_session()

            sessions.append(
                empty_session_id
            )

            set_session_status(
                empty_session_id,
                "reporting",
            )

            empty_lease = acquire_lease(
                empty_session_id
            )

            empty_report = make_report()

            empty_report.title = (
                "Insufficient Evidence Report"
            )

            empty_report.executive_summary = (
                "Insufficient evidence was available."
            )

            for section in empty_report.sections:

                section.content = (
                    "No usable research evidence was available."
                )

            empty_report.conclusions = (
                "No supported conclusions can be drawn."
            )

            empty_report.limitations = [
                "No usable research evidence."
            ]

            empty_report_id = persist_report(
                empty_session_id,
                empty_report,
                empty_lease,
            )

            empty_persisted_report = load_report(
                empty_session_id
            )

            assert empty_persisted_report is not None

            assert (
                empty_persisted_report.id
                == empty_report_id
            )

            empty_output_path = (
                output_directory
                / f"{empty_session_id}.txt"
            )

            execute_node(
                node=node,
                session_id=empty_session_id,
                lease=empty_lease,
            )

            assert (
                get_session_snapshot(empty_session_id)[0]
                == "completed"
            )

            assert empty_output_path.is_file()

            empty_report_text = (
                empty_output_path.read_text(
                    encoding="utf-8"
                )
            )

            assert (
                empty_report_text.count(
                    "Sources cited: None"
                ) == 2
            )

            assert (
                "Contradicting evidence:"
                not in empty_report_text
            )

            assert (
                "BIBLIOGRAPHY"
                in empty_report_text
            )

            bibliography_text = (
                empty_report_text.split(
                    "BIBLIOGRAPHY",
                    1,
                )[1]
            )

            assert not (
                bibliography_text.strip("- \r\n\t")
            )

            assert (
                load_report(empty_session_id)
                == empty_persisted_report
            )

            assert (
                get_session_snapshot(session_id)
                == completed_snapshot
            )

            assert (
                output_path.read_bytes()
                == published_content
            )

            assert set(
                output_directory.iterdir()
            ) == {
                output_path,
                empty_output_path,
            }

            print(
                "TEST 13 - Report without citations completed: PASSED"
            )

            with SessionLocal() as db:

                repository = (
                    ExecutionLeaseRepository(
                        db
                    )
                )

                assert repository.release(
                    replacement_lease
                ) is True

                assert repository.release(
                    empty_lease
                ) is True

    finally:

        for session_id in reversed(
            sessions
        ):

            delete_report(
                session_id
            )

            delete_provenance(
                session_id
            )

            delete_session(
                session_id
            )

    print()

    print("PASS")


if __name__ == "__main__":

    main()