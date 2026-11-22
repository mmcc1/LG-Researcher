from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from processing.report_citation_resolver import (
    ReportCitationResolver,
)


SESSION_ID = "citation-test-session"

QUESTION_ID = 10

CLAIM_ID = 100


def make_finding(
    finding_id=101,
    source_id=201,
    question_id=QUESTION_ID,
):

    return SimpleNamespace(
        id=finding_id,
        source_id=source_id,
        research_question_id=question_id,
    )


def make_source(
    source_id=201,
    session_id=SESSION_ID,
    question_id=QUESTION_ID,
    title="Test citation source",
    extracted_text="Valid research evidence.",
):

    url = (
        f"https://example.com/source/{source_id}"
    )

    return SimpleNamespace(
        id=source_id,
        research_session_id=session_id,
        research_question_id=question_id,
        title=title,
        requested_url=url,
        final_url=url,
        extracted_text=extracted_text,
        content_hash="0" * 64,
    )


def make_row(
    claim_id=CLAIM_ID,
    finding=None,
    source=None,
):

    finding_id = (
        finding.id
        if finding is not None
        else 101
    )

    return (
        claim_id,
        finding_id,
        QUESTION_ID,
        finding,
        source,
    )


def make_valid_row(
    finding_id=101,
    source_id=201,
    claim_id=CLAIM_ID,
    title="Test citation source",
):

    finding = make_finding(
        finding_id=finding_id,
        source_id=source_id,
    )

    source = make_source(
        source_id=source_id,
        title=title,
    )

    return make_row(
        claim_id=claim_id,
        finding=finding,
        source=source,
    )


def make_resolver(
    supporting_rows,
    contradicting_rows,
    claim_ids=None,
):

    if claim_ids is None:

        claim_ids = [
            CLAIM_ID
        ]

    db = Mock()

    claim_query = Mock()

    claim_query.join.return_value = (
        claim_query
    )

    claim_query.filter.return_value = (
        claim_query
    )

    claim_query.all.return_value = [
        (claim_id,)
        for claim_id in claim_ids
    ]

    supporting_query = Mock()

    contradicting_query = Mock()

    for query, rows in (
        (
            supporting_query,
            supporting_rows,
        ),
        (
            contradicting_query,
            contradicting_rows,
        ),
    ):

        query.select_from.return_value = query
        query.join.return_value = query
        query.outerjoin.return_value = query
        query.filter.return_value = query
        query.order_by.return_value = query

        query.all.return_value = rows

    db.query.side_effect = [
        claim_query,
        supporting_query,
        contradicting_query,
    ]

    resolver = ReportCitationResolver(
        db
    )

    return resolver, db


def resolve_claim(
    resolver,
):

    return resolver.resolve(
        session_id=SESSION_ID,
        reviewed_claim_ids=[
            CLAIM_ID
        ],
    )


def test_empty_claim_collection():

    db = Mock()

    resolver = ReportCitationResolver(
        db
    )

    provenance = resolver.resolve(
        session_id=SESSION_ID,
        reviewed_claim_ids=[],
    )

    assert (
        provenance.research_session_id
        == SESSION_ID
    )

    assert provenance.claims == []

    db.query.assert_not_called()


def test_valid_supporting_and_contradicting_sources():

    resolver, db = make_resolver(
        supporting_rows=[
            make_valid_row(
                finding_id=101,
                source_id=201,
            )
        ],
        contradicting_rows=[
            make_valid_row(
                finding_id=102,
                source_id=202,
            )
        ],
    )

    provenance = resolve_claim(
        resolver
    )

    assert len(provenance.claims) == 1

    claim = provenance.claims[0]

    assert claim.reviewed_claim_id == CLAIM_ID

    assert [
        source.source_id
        for source in claim.supporting_sources
    ] == [201]

    assert [
        source.source_id
        for source in claim.contradicting_sources
    ] == [202]

    assert db.query.call_count == 3


def test_supporting_evidence_without_contradictions():

    resolver, _ = make_resolver(
        supporting_rows=[
            make_valid_row()
        ],
        contradicting_rows=[],
    )

    provenance = resolve_claim(
        resolver
    )

    claim = provenance.claims[0]

    assert len(claim.supporting_sources) == 1

    assert claim.contradicting_sources == []


def test_foreign_reviewed_claim_rejected():

    resolver, db = make_resolver(
        supporting_rows=[],
        contradicting_rows=[],
        claim_ids=[],
    )

    with pytest.raises(
        ValueError,
        match=(
            "Reviewed claims do not belong "
            "to the requested research session: "
            "100"
        ),
    ):

        resolve_claim(
            resolver
        )

    assert db.query.call_count == 1


def test_claim_without_supporting_sources_rejected():

    resolver, _ = make_resolver(
        supporting_rows=[],
        contradicting_rows=[
            make_valid_row()
        ],
    )

    with pytest.raises(
        ValueError,
        match=(
            "Reviewed claim has no resolvable "
            "supporting source: 100"
        ),
    ):

        resolve_claim(
            resolver
        )


@pytest.mark.parametrize(
    "title",
    [
        "",
        " ",
        "\t\r\n ",
        None,
    ],
)
def test_untitled_source_accepted(
    title,
):

    resolver, _ = make_resolver(
        supporting_rows=[
            make_valid_row(
                title=title,
            )
        ],
        contradicting_rows=[],
    )

    provenance = resolve_claim(
        resolver
    )

    source = (
        provenance.claims[0]
        .supporting_sources[0]
    )

    assert source.title == (
        title or ""
    )

    assert source.final_url == (
        "https://example.com/source/201"
    )

    assert source.content_hash == (
        "0" * 64
    )


def make_invalid_row(
    invalid_condition,
):

    finding = make_finding(
        finding_id=102,
        source_id=202,
    )

    source = make_source(
        source_id=202,
    )

    if invalid_condition == "missing_finding":

        return (
            CLAIM_ID,
            finding.id,
            QUESTION_ID,
            None,
            None,
        )

    if invalid_condition == "foreign_finding":

        finding.research_question_id = 999

    elif invalid_condition == "missing_source":

        source = None

    elif invalid_condition == "foreign_source_question":

        source.research_question_id = 999

    elif invalid_condition == "foreign_source_session":

        source.research_session_id = (
            "foreign-session"
        )

    elif invalid_condition == "empty_content":

        source.extracted_text = ""

    elif invalid_condition == "whitespace_content":

        source.extracted_text = "\t\r\n "

    elif invalid_condition == "null_content":

        source.extracted_text = None

    else:

        raise AssertionError(
            f"Unknown condition: {invalid_condition}"
        )

    return make_row(
        finding=finding,
        source=source,
    )


@pytest.mark.parametrize(
    "relationship",
    [
        "supporting",
        "contradicting",
    ],
)
@pytest.mark.parametrize(
    "invalid_condition, expected_message",
    [
        (
            "missing_finding",
            "references a missing finding: 102",
        ),
        (
            "foreign_finding",
            "finding 102 belonging to "
            "another research question.",
        ),
        (
            "missing_source",
            "references a missing source: 202",
        ),
        (
            "foreign_source_question",
            "source 202 outside the "
            "current research question.",
        ),
        (
            "foreign_source_session",
            "source 202 outside the "
            "current research question.",
        ),
        (
            "empty_content",
            "a source containing no usable "
            "research text: 202",
        ),
        (
            "whitespace_content",
            "a source containing no usable "
            "research text: 202",
        ),
        (
            "null_content",
            "a source containing no usable "
            "research text: 202",
        ),
    ],
)
def test_invalid_citation_evidence_rejected(
    relationship,
    invalid_condition,
    expected_message,
):

    supporting_rows = [
        make_valid_row()
    ]

    contradicting_rows = []

    invalid_row = make_invalid_row(
        invalid_condition
    )

    if relationship == "supporting":

        supporting_rows.append(
            invalid_row
        )

    else:

        contradicting_rows.append(
            invalid_row
        )

    resolver, _ = make_resolver(
        supporting_rows=supporting_rows,
        contradicting_rows=contradicting_rows,
    )

    with pytest.raises(
        ValueError
    ) as error:

        resolve_claim(
            resolver
        )

    assert expected_message in str(
        error.value
    )


def test_duplicate_sources_eliminated():

    resolver, _ = make_resolver(
        supporting_rows=[
            make_valid_row(
                finding_id=101,
                source_id=201,
            ),
            make_valid_row(
                finding_id=102,
                source_id=201,
            ),
            make_valid_row(
                finding_id=103,
                source_id=202,
            ),
        ],
        contradicting_rows=[],
    )

    provenance = resolve_claim(
        resolver
    )

    sources = (
        provenance.claims[0]
        .supporting_sources
    )

    assert [
        source.source_id
        for source in sources
    ] == [
        201,
        202,
    ]


def test_invalid_relationship_not_hidden_by_deduplication():

    valid_row = make_valid_row(
        finding_id=101,
        source_id=201,
    )

    invalid_finding = make_finding(
        finding_id=102,
        source_id=201,
        question_id=999,
    )

    source = make_source(
        source_id=201,
    )

    invalid_row = make_row(
        finding=invalid_finding,
        source=source,
    )

    resolver, _ = make_resolver(
        supporting_rows=[
            valid_row,
            invalid_row,
        ],
        contradicting_rows=[],
    )

    with pytest.raises(
        ValueError,
        match=(
            "finding 102 belonging to "
            "another research question."
        ),
    ):

        resolve_claim(
            resolver
        )


def test_claim_order_preserved_and_duplicates_removed():

    resolver, _ = make_resolver(
        supporting_rows=[
            make_valid_row(
                claim_id=100,
                finding_id=101,
                source_id=201,
            ),
            make_valid_row(
                claim_id=200,
                finding_id=102,
                source_id=202,
            ),
        ],
        contradicting_rows=[],
        claim_ids=[
            100,
            200,
        ],
    )

    provenance = resolver.resolve(
        session_id=SESSION_ID,
        reviewed_claim_ids=[
            200,
            100,
            200,
        ],
    )

    assert [
        claim.reviewed_claim_id
        for claim in provenance.claims
    ] == [
        200,
        100,
    ]


def test_source_metadata_preserved():

    resolver, _ = make_resolver(
        supporting_rows=[
            make_valid_row()
        ],
        contradicting_rows=[],
    )

    provenance = resolve_claim(
        resolver
    )

    source = (
        provenance.claims[0]
        .supporting_sources[0]
    )

    assert source.source_id == 201

    assert source.title == (
        "Test citation source"
    )

    assert source.requested_url == (
        "https://example.com/source/201"
    )

    assert source.final_url == (
        "https://example.com/source/201"
    )

    assert source.content_hash == (
        "0" * 64
    )