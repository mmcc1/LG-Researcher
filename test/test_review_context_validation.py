from types import SimpleNamespace

import pytest

from processing.review_context_builder import (
    ReviewContextBuilder,
)


def make_finding(
    finding_id=101,
    source_id=201,
):

    return SimpleNamespace(
        id=finding_id,
        source_id=source_id,
        claim="Test research claim.",
        evidence="Test supporting evidence.",
        relevance="Relevant to the research question.",
        confidence="high",
    )


def make_source(
    source_id=201,
    title="Test research source",
    extracted_text="Test source content.",
):

    return SimpleNamespace(
        id=source_id,
        title=title,
        final_url=(
            f"https://example.com/source/{source_id}"
        ),
        extracted_text=extracted_text,
    )


def test_valid_evidence_context():

    builder = ReviewContextBuilder()

    finding = make_finding()

    source = make_source()

    context = builder.build(
        findings=[finding],
        sources_by_id={
            source.id: source,
        },
    )

    assert "FINDING ID: 101" in context
    assert "SOURCE ID: 201" in context
    assert "SOURCE TITLE: Test research source" in context

    assert (
        "SOURCE URL: https://example.com/source/201"
        in context
    )

    assert finding.claim in context
    assert finding.evidence in context
    assert finding.relevance in context

    assert "EXTRACTION CONFIDENCE: high" in context


def test_empty_findings_produce_empty_context():

    builder = ReviewContextBuilder()

    context = builder.build(
        findings=[],
        sources_by_id={},
    )

    assert context == ""


def test_missing_source_rejected():

    builder = ReviewContextBuilder()

    finding = make_finding()

    with pytest.raises(
        ValueError,
        match=(
            "Finding 101 references "
            "a missing source: 201"
        ),
    ):

        builder.build(
            findings=[finding],
            sources_by_id={},
        )


@pytest.mark.parametrize(
    "extracted_text",
    [
        "",
        " ",
        "\t\r\n ",
        None,
    ],
)
def test_unusable_source_rejected(
    extracted_text,
):

    builder = ReviewContextBuilder()

    finding = make_finding()

    source = make_source(
        extracted_text=extracted_text,
    )

    with pytest.raises(
        ValueError,
        match=(
            "Finding 101 references "
            "a source containing no usable "
            "research text: 201"
        ),
    ):

        builder.build(
            findings=[finding],
            sources_by_id={
                source.id: source,
            },
        )


@pytest.mark.parametrize(
    "title",
    [
        "",
        " ",
        "\t\r\n ",
    ],
)
def test_untitled_source_uses_url(
    title,
):

    builder = ReviewContextBuilder()

    finding = make_finding()

    source = make_source(
        title=title,
    )

    context = builder.build(
        findings=[finding],
        sources_by_id={
            source.id: source,
        },
    )

    assert (
        f"SOURCE TITLE: {source.final_url}"
        in context
    )

    assert (
        f"SOURCE URL: {source.final_url}"
        in context
    )

    assert finding.evidence in context


def test_multiple_valid_findings_preserve_order():

    builder = ReviewContextBuilder()

    first_finding = make_finding(
        finding_id=101,
        source_id=201,
    )

    second_finding = make_finding(
        finding_id=102,
        source_id=202,
    )

    first_source = make_source(
        source_id=201,
    )

    second_source = make_source(
        source_id=202,
    )

    context = builder.build(
        findings=[
            first_finding,
            second_finding,
        ],
        sources_by_id={
            first_source.id: first_source,
            second_source.id: second_source,
        },
    )

    first_position = context.index(
        "FINDING ID: 101"
    )

    second_position = context.index(
        "FINDING ID: 102"
    )

    assert first_position < second_position

    assert context.count(
        "================================"
    ) == 1


def test_invalid_finding_prevents_partial_context():

    builder = ReviewContextBuilder()

    first_finding = make_finding(
        finding_id=101,
        source_id=201,
    )

    second_finding = make_finding(
        finding_id=102,
        source_id=202,
    )

    first_source = make_source(
        source_id=201,
    )

    second_source = make_source(
        source_id=202,
        extracted_text="",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Finding 102 references "
            "a source containing no usable "
            "research text: 202"
        ),
    ):

        builder.build(
            findings=[
                first_finding,
                second_finding,
            ],
            sources_by_id={
                first_source.id: first_source,
                second_source.id: second_source,
            },
        )


def test_unreferenced_invalid_source_is_ignored():

    builder = ReviewContextBuilder()

    finding = make_finding(
        finding_id=101,
        source_id=201,
    )

    valid_source = make_source(
        source_id=201,
    )

    invalid_source = make_source(
        source_id=202,
        extracted_text="",
    )

    context = builder.build(
        findings=[finding],
        sources_by_id={
            valid_source.id: valid_source,
            invalid_source.id: invalid_source,
        },
    )

    assert "FINDING ID: 101" in context
    assert "SOURCE ID: 201" in context
    assert "SOURCE ID: 202" not in context