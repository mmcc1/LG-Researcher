from contextlib import contextmanager

from persistence.database import (
    SessionLocal,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
)

from persistence.models import (
    Finding,
    Source,
    ReviewedClaimEntity,
    ReviewedClaimSupport,
    ReviewedClaimContradiction,
)

from domain.report import (
    PersistedResearchReport,
    PersistedReportSection,
)

from processing.report_citation_resolver import (
    ReportCitationResolver,
)

from processing.report_citation_registry import (
    ReportCitationRegistry,
)

from test_search_result_fencing import (
    create_session,
    delete_session,
)

from test_review_selection_fencing import (
    create_review_question,
)

from test_review_persistence_fencing import (
    save_review,
    get_snapshot,
)

from test_review_provenance_fencing import (
    create_source_and_findings,
    make_review,
    get_provenance_snapshot,
    delete_provenance,
)


TEST_DATABASE = "Researcher"


def validate_database():

    with SessionLocal() as db:

        engine = db.get_bind()

        if engine.url.database != TEST_DATABASE:

            raise RuntimeError(
                "Integration test requires the "
                "Researcher development database."
            )


@contextmanager
def temporary_database_changes():

    with SessionLocal() as db:

        try:

            yield db

        finally:

            db.rollback()


def get_reviewed_claim_ids(
    review_id,
):

    with SessionLocal() as db:

        rows = (
            db.query(
                ReviewedClaimEntity.id
            )
            .filter(
                ReviewedClaimEntity.question_review_id
                == review_id
            )
            .order_by(
                ReviewedClaimEntity.id
            )
            .all()
        )

        return [
            row[0]
            for row in rows
        ]


def resolve_citations(
    session_id,
    claim_ids,
):

    with SessionLocal() as db:

        resolver = ReportCitationResolver(
            db
        )

        provenance = resolver.resolve(
            session_id=session_id,
            reviewed_claim_ids=claim_ids,
        )

        return provenance


def expect_resolution_rejected(
    db,
    session_id,
    claim_ids,
    expected_message,
):

    resolver = ReportCitationResolver(
        db
    )

    try:

        resolver.resolve(
            session_id=session_id,
            reviewed_claim_ids=claim_ids,
        )

    except ValueError as exc:

        assert expected_message in str(exc), (
            f"Unexpected rejection reason: {exc}"
        )

    else:

        raise AssertionError(
            "Invalid citation provenance "
            "was unexpectedly accepted."
        )


def expect_invalid_source_content_rejected(
    session_id,
    question_id,
    claim_ids,
    source_id,
    extracted_text,
):

    with temporary_database_changes() as db:

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

        db.flush()

        expect_resolution_rejected(
            db=db,
            session_id=session_id,
            claim_ids=claim_ids,
            expected_message=(
                "a source containing no usable "
                f"research text: {source_id}"
            ),
        )


def expect_foreign_finding_rejected(
    session_id,
    question_id,
    reviewed_claim_id,
    original_finding_id,
    foreign_finding_id,
    foreign_question_id,
    association_model,
):

    with temporary_database_changes() as db:

        original_finding = db.get(
            Finding,
            original_finding_id,
        )

        foreign_finding = db.get(
            Finding,
            foreign_finding_id,
        )

        assert original_finding is not None

        assert foreign_finding is not None

        assert (
            original_finding.research_question_id
            == question_id
        )

        assert (
            foreign_finding.research_question_id
            == foreign_question_id
        )

        assert foreign_question_id != question_id

        claim = db.get(
            ReviewedClaimEntity,
            reviewed_claim_id,
        )

        assert claim is not None

        association = db.get(
            association_model,
            (
                reviewed_claim_id,
                original_finding_id,
            ),
        )

        assert association is not None

        db.delete(
            association
        )

        db.flush()

        replacement = association_model(
            reviewed_claim_id=reviewed_claim_id,
            finding_id=foreign_finding_id,
        )

        db.add(
            replacement
        )

        db.flush()

        expect_resolution_rejected(
            db=db,
            session_id=session_id,
            claim_ids=[
                reviewed_claim_id
            ],
            expected_message=(
                f"finding {foreign_finding_id} "
                "belonging to another "
                "research question."
            ),
        )


def expect_foreign_source_rejected(
    session_id,
    question_id,
    reviewed_claim_id,
    finding_id,
    foreign_question_id,
    foreign_source_id,
):

    with temporary_database_changes() as db:

        finding = db.get(
            Finding,
            finding_id,
        )

        foreign_source = db.get(
            Source,
            foreign_source_id,
        )

        assert finding is not None

        assert foreign_source is not None

        assert (
            finding.research_question_id
            == question_id
        )

        assert (
            foreign_source.research_session_id
            == session_id
        )

        assert (
            foreign_source.research_question_id
            == foreign_question_id
        )

        assert foreign_question_id != question_id

        finding.source_id = (
            foreign_source_id
        )

        db.flush()

        expect_resolution_rejected(
            db=db,
            session_id=session_id,
            claim_ids=[
                reviewed_claim_id
            ],
            expected_message=(
                f"source {foreign_source_id} "
                "outside the current "
                "research question."
            ),
        )


def expect_missing_support_rejected(
    session_id,
    reviewed_claim_id,
):

    with temporary_database_changes() as db:

        deleted_count = (
            db.query(
                ReviewedClaimSupport
            )
            .filter(
                ReviewedClaimSupport.reviewed_claim_id
                == reviewed_claim_id
            )
            .delete(
                synchronize_session=False
            )
        )

        assert deleted_count > 0

        db.flush()

        expect_resolution_rejected(
            db=db,
            session_id=session_id,
            claim_ids=[
                reviewed_claim_id
            ],
            expected_message=(
                "Reviewed claim has no resolvable "
                "supporting source: "
                f"{reviewed_claim_id}"
            ),
        )


def assert_evidence_unchanged(
    session_id,
    question_id,
    claim_ids,
    expected_provenance,
    expected_snapshot,
    expected_citations,
):

    assert get_provenance_snapshot(
        question_id
    ) == expected_provenance

    assert get_snapshot(
        question_id
    ) == expected_snapshot

    current_citations = (
        resolve_citations(
            session_id=session_id,
            claim_ids=claim_ids,
        )
    )

    assert (
        current_citations.model_dump()
        == expected_citations.model_dump()
    ), (
        "Original citation provenance "
        "has changed."
    )


def test_registry_integration(
    session_id,
    claim_ids,
    provenance,
    untitled_source_id,
):

    report = PersistedResearchReport(
        id=1,
        research_session_id=session_id,
        title="Disposable citation test report",
        executive_summary="Test executive summary.",
        sections=[
            PersistedReportSection(
                id=1,
                ordinal=1,
                heading="Test report section",
                content="Test evidence narrative.",
                reviewed_claim_ids=claim_ids,
            ),
        ],
        conclusions="Test conclusions.",
        limitations=[],
    )

    registry = ReportCitationRegistry()

    result = registry.build(
        report=report,
        provenance=provenance,
    )

    repeated_result = registry.build(
        report=report,
        provenance=provenance,
    )

    assert (
        result.model_dump()
        == repeated_result.model_dump()
    )

    assert len(
        result.bibliography
    ) == 2

    assert len(
        result.sections
    ) == 1

    untitled_entries = [
        entry
        for entry in result.bibliography
        if untitled_source_id in entry.source_ids
    ]

    assert len(
        untitled_entries
    ) == 1

    untitled_entry = (
        untitled_entries[0]
    )

    assert (
        untitled_entry.title
        == untitled_entry.url
    )

    section = result.sections[0]

    assert section.supporting_numbers == [
        1
    ]

    assert section.contradicting_numbers == [
        2
    ]

    assert untitled_entry.number == 2

    assert untitled_entry.number in (
        section.contradicting_numbers
    )


def main():

    print()

    print(
        "REPORT CITATION RESOLVER SQL INTEGRATION"
    )

    print(
        "========================================"
    )

    validate_database()

    sessions = []

    try:

        session_id = create_session()

        sessions.append(
            session_id
        )

        other_session_id = create_session()

        sessions.append(
            other_session_id
        )

        question_id = create_review_question(
            session_id,
            "reviewing",
        )

        foreign_question_id = (
            create_review_question(
                session_id,
                "reviewing",
            )
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

        foreign_source_id, foreign_finding_ids = (
            create_source_and_findings(
                session_id=session_id,
                question_id=foreign_question_id,
                count=1,
            )
        )

        finding_ids = (
            supporting_ids
            + contradicting_ids
        )

        with SessionLocal() as db:

            lease = ExecutionLeaseRepository(
                db
            ).acquire(
                session_id,
                duration_seconds=300,
            )

        assert lease is not None

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

        with SessionLocal() as db:

            released = ExecutionLeaseRepository(
                db
            ).release(
                lease
            )

        assert released is True

        claim_ids = get_reviewed_claim_ids(
            review_id
        )

        assert len(claim_ids) == 2

        first_claim_id = claim_ids[0]

        expected_snapshot = get_snapshot(
            question_id
        )

        assert expected_snapshot[0] == "reviewed"

        expected_provenance = {
            "reviews": 1,
            "claims": 2,
            "supports": 3,
            "contradicting_references": 1,
            "contradictions": 1,
            "gaps": 2,
        }

        assert get_provenance_snapshot(
            question_id
        ) == expected_provenance

        expected_citations = resolve_citations(
            session_id=session_id,
            claim_ids=claim_ids,
        )

        def verify_original_evidence():

            assert_evidence_unchanged(
                session_id=session_id,
                question_id=question_id,
                claim_ids=claim_ids,
                expected_provenance=expected_provenance,
                expected_snapshot=expected_snapshot,
                expected_citations=expected_citations,
            )

        #
        # Resolve provenance through the actual
        # persisted evidence relationships.
        #

        assert (
            expected_citations.research_session_id
            == session_id
        )

        assert len(
            expected_citations.claims
        ) == 2

        first_claim = (
            expected_citations.claims[0]
        )

        second_claim = (
            expected_citations.claims[1]
        )

        assert (
            first_claim.reviewed_claim_id
            == first_claim_id
        )

        assert [
            source.source_id
            for source in first_claim.supporting_sources
        ] == [
            supporting_source_id
        ]

        assert [
            source.source_id
            for source in first_claim.contradicting_sources
        ] == [
            contradicting_source_id
        ]

        assert [
            source.source_id
            for source in second_claim.supporting_sources
        ] == [
            supporting_source_id
        ]

        assert not (
            second_claim.contradicting_sources
        )

        print(
            "TEST 1 - Valid persisted provenance: PASSED"
        )

        #
        # Multiple supporting findings refer
        # to the same underlying source.
        #

        with SessionLocal() as db:

            supporting_count = (
                db.query(
                    ReviewedClaimSupport
                )
                .filter(
                    ReviewedClaimSupport.reviewed_claim_id
                    == first_claim_id
                )
                .count()
            )

        assert supporting_count == 2

        assert len(
            first_claim.supporting_sources
        ) == 1

        print(
            "TEST 2 - Duplicate sources eliminated: PASSED"
        )

        #
        # Untitled documents remain valid
        # when usable research text exists.
        #

        untitled_source = (
            first_claim.contradicting_sources[0]
        )

        assert untitled_source.title == ""

        assert (
            untitled_source.source_id
            == contradicting_source_id
        )

        with SessionLocal() as db:

            source = db.get(
                Source,
                contradicting_source_id,
            )

            assert source.extracted_text.strip()

            assert (
                untitled_source.final_url
                == source.final_url
            )

        print(
            "TEST 3 - Valid untitled source accepted: PASSED"
        )

        #
        # A reviewed claim must not be resolved
        # using another research session.
        #

        with SessionLocal() as db:

            expect_resolution_rejected(
                db=db,
                session_id=other_session_id,
                claim_ids=[
                    first_claim_id
                ],
                expected_message=(
                    "Reviewed claims do not belong "
                    "to the requested research session: "
                    f"{first_claim_id}"
                ),
            )

        verify_original_evidence()

        print(
            "TEST 4 - Foreign reviewed claim rejected: PASSED"
        )

        expect_invalid_source_content_rejected(
            session_id=session_id,
            question_id=question_id,
            claim_ids=claim_ids,
            source_id=supporting_source_id,
            extracted_text="",
        )

        verify_original_evidence()

        print(
            "TEST 5 - Empty supporting source rejected: PASSED"
        )

        expect_invalid_source_content_rejected(
            session_id=session_id,
            question_id=question_id,
            claim_ids=claim_ids,
            source_id=contradicting_source_id,
            extracted_text="",
        )

        verify_original_evidence()

        print(
            "TEST 6 - Empty contradicting source rejected: PASSED"
        )

        expect_invalid_source_content_rejected(
            session_id=session_id,
            question_id=question_id,
            claim_ids=claim_ids,
            source_id=supporting_source_id,
            extracted_text="\t\r\n ",
        )

        verify_original_evidence()

        print(
            "TEST 7 - Whitespace supporting source rejected: PASSED"
        )

        expect_invalid_source_content_rejected(
            session_id=session_id,
            question_id=question_id,
            claim_ids=claim_ids,
            source_id=contradicting_source_id,
            extracted_text="\t\r\n ",
        )

        verify_original_evidence()

        print(
            "TEST 8 - Whitespace contradicting source rejected: PASSED"
        )

        #
        # The foreign finding has valid database
        # keys but belongs to another question.
        #

        expect_foreign_finding_rejected(
            session_id=session_id,
            question_id=question_id,
            reviewed_claim_id=first_claim_id,
            original_finding_id=supporting_ids[0],
            foreign_finding_id=foreign_finding_ids[0],
            foreign_question_id=foreign_question_id,
            association_model=ReviewedClaimSupport,
        )

        verify_original_evidence()

        print(
            "TEST 9 - Foreign supporting finding rejected: PASSED"
        )

        expect_foreign_finding_rejected(
            session_id=session_id,
            question_id=question_id,
            reviewed_claim_id=first_claim_id,
            original_finding_id=contradicting_ids[0],
            foreign_finding_id=foreign_finding_ids[0],
            foreign_question_id=foreign_question_id,
            association_model=ReviewedClaimContradiction,
        )

        verify_original_evidence()

        print(
            "TEST 10 - Foreign contradicting finding rejected: PASSED"
        )

        #
        # The finding belongs to the correct
        # question but references a foreign source.
        #

        expect_foreign_source_rejected(
            session_id=session_id,
            question_id=question_id,
            reviewed_claim_id=first_claim_id,
            finding_id=supporting_ids[0],
            foreign_question_id=foreign_question_id,
            foreign_source_id=foreign_source_id,
        )

        verify_original_evidence()

        print(
            "TEST 11 - Foreign supporting source rejected: PASSED"
        )

        expect_foreign_source_rejected(
            session_id=session_id,
            question_id=question_id,
            reviewed_claim_id=first_claim_id,
            finding_id=contradicting_ids[0],
            foreign_question_id=foreign_question_id,
            foreign_source_id=foreign_source_id,
        )

        verify_original_evidence()

        print(
            "TEST 12 - Foreign contradicting source rejected: PASSED"
        )

        expect_missing_support_rejected(
            session_id=session_id,
            reviewed_claim_id=first_claim_id,
        )

        verify_original_evidence()

        print(
            "TEST 13 - Claim without supporting evidence rejected: PASSED"
        )

        #
        # Confirm that all temporary changes
        # have been rolled back successfully.
        #

        restored_citations = resolve_citations(
            session_id=session_id,
            claim_ids=claim_ids,
        )

        assert (
            restored_citations.model_dump()
            == expected_citations.model_dump()
        )

        verify_original_evidence()

        print(
            "TEST 14 - Original evidence restored: PASSED"
        )

        #
        # Pass provenance obtained from SQL
        # directly into the production registry.
        #

        test_registry_integration(
            session_id=session_id,
            claim_ids=claim_ids,
            provenance=restored_citations,
            untitled_source_id=contradicting_source_id,
        )

        verify_original_evidence()

        print(
            "TEST 15 - Resolver and registry integration: PASSED"
        )

        print()

        print("PASS")

    finally:

        for disposable_session_id in reversed(
            sessions
        ):

            delete_provenance(
                disposable_session_id
            )

            delete_session(
                disposable_session_id
            )


if __name__ == "__main__":

    main()