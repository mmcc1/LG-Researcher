import pytest

from domain.report import (
    PersistedReportSection,
    PersistedResearchReport,
)

from domain.report_citation import (
    CitationSource,
    ClaimSourceProvenance,
    ReportCitationProvenance,
)

from processing.report_citation_registry import (
    ReportCitationRegistry,
)


SESSION_ID = "citation-registry-test-session"


def make_source(
    source_id=201,
    title="Test research source",
    final_url=None,
):

    if final_url is None:

        final_url = (
            f"https://example.com/source/{source_id}"
        )

    return CitationSource(
        source_id=source_id,
        title=title,
        requested_url=final_url,
        final_url=final_url,
        content_hash="0" * 64,
    )


def make_claim(
    claim_id=100,
    supporting_sources=None,
    contradicting_sources=None,
):

    if supporting_sources is None:

        supporting_sources = [
            make_source()
        ]

    if contradicting_sources is None:

        contradicting_sources = []

    return ClaimSourceProvenance(
        reviewed_claim_id=claim_id,
        supporting_sources=supporting_sources,
        contradicting_sources=contradicting_sources,
    )


def make_section(
    section_id=301,
    ordinal=1,
    claim_ids=None,
):

    if claim_ids is None:

        claim_ids = [100]

    return PersistedReportSection(
        id=section_id,
        ordinal=ordinal,
        heading=f"Test section {section_id}",
        content="Evidence-based test narrative.",
        reviewed_claim_ids=claim_ids,
    )


def make_report(
    sections=None,
    session_id=SESSION_ID,
):

    if sections is None:

        sections = [
            make_section()
        ]

    return PersistedResearchReport(
        id=1,
        research_session_id=session_id,
        title="Test research report",
        executive_summary="Test executive summary.",
        sections=sections,
        conclusions="Test conclusions.",
        limitations=[],
    )


def make_provenance(
    claims=None,
    session_id=SESSION_ID,
):

    if claims is None:

        claims = [
            make_claim()
        ]

    return ReportCitationProvenance(
        research_session_id=session_id,
        claims=claims,
    )


def build_registry(
    report=None,
    provenance=None,
):

    if report is None:

        report = make_report()

    if provenance is None:

        provenance = make_provenance()

    registry = ReportCitationRegistry()

    return registry.build(
        report=report,
        provenance=provenance,
    )


def test_valid_citation_registry():

    result = build_registry()

    assert (
        result.research_session_id
        == SESSION_ID
    )

    assert len(result.sections) == 1

    assert len(result.bibliography) == 1

    section = result.sections[0]

    entry = result.bibliography[0]

    assert section.section_id == 301
    assert section.ordinal == 1
    assert section.supporting_numbers == [1]
    assert section.contradicting_numbers == []

    assert entry.number == 1
    assert entry.title == "Test research source"

    assert entry.url == (
        "https://example.com/source/201"
    )

    assert entry.source_ids == [201]


def test_empty_report_and_provenance():

    report = make_report(
        sections=[],
    )

    provenance = make_provenance(
        claims=[],
    )

    result = build_registry(
        report=report,
        provenance=provenance,
    )

    assert result.sections == []

    assert result.bibliography == []


def test_section_without_claims():

    report = make_report(
        sections=[
            make_section(
                claim_ids=[],
            )
        ],
    )

    provenance = make_provenance(
        claims=[],
    )

    result = build_registry(
        report=report,
        provenance=provenance,
    )

    assert len(result.sections) == 1

    assert (
        result.sections[0].supporting_numbers
        == []
    )

    assert (
        result.sections[0].contradicting_numbers
        == []
    )

    assert result.bibliography == []


@pytest.mark.parametrize(
    "title",
    [
        "",
        " ",
        "\t\r\n ",
    ],
)
@pytest.mark.parametrize(
    "relationship",
    [
        "supporting",
        "contradicting",
    ],
)
def test_untitled_source_uses_normalized_url(
    title,
    relationship,
):

    source = make_source(
        source_id=202,
        title=title,
        final_url=(
            "HTTPS://EXAMPLE.COM:443/"
            "article?version=2#section"
        ),
    )

    expected_url = (
        "https://example.com/article?version=2"
    )

    if relationship == "supporting":

        claim = make_claim(
            supporting_sources=[
                source
            ],
        )

    else:

        claim = make_claim(
            supporting_sources=[
                make_source()
            ],
            contradicting_sources=[
                source
            ],
        )

    provenance = make_provenance(
        claims=[
            claim
        ],
    )

    result = build_registry(
        provenance=provenance,
    )

    entry = next(
        entry
        for entry in result.bibliography
        if 202 in entry.source_ids
    )

    assert entry.title == expected_url

    assert entry.url == expected_url

    assert entry.source_ids == [202]

    section = result.sections[0]

    if relationship == "supporting":

        assert (
            section.supporting_numbers
            == [entry.number]
        )

    else:

        assert (
            section.contradicting_numbers
            == [entry.number]
        )


def test_valid_title_preserved_and_trimmed():

    source = make_source(
        title="  Original publication title  ",
    )

    provenance = make_provenance(
        claims=[
            make_claim(
                supporting_sources=[
                    source
                ],
            )
        ],
    )

    result = build_registry(
        provenance=provenance,
    )

    assert (
        result.bibliography[0].title
        == "Original publication title"
    )


def test_supporting_and_contradicting_references():

    supporting_source = make_source(
        source_id=201,
    )

    contradicting_source = make_source(
        source_id=202,
    )

    provenance = make_provenance(
        claims=[
            make_claim(
                supporting_sources=[
                    supporting_source
                ],
                contradicting_sources=[
                    contradicting_source
                ],
            )
        ],
    )

    result = build_registry(
        provenance=provenance,
    )

    section = result.sections[0]

    assert section.supporting_numbers == [1]

    assert section.contradicting_numbers == [2]

    assert [
        entry.source_ids
        for entry in result.bibliography
    ] == [
        [201],
        [202],
    ]


def test_duplicate_urls_share_bibliography_entry():

    first_source = make_source(
        source_id=201,
        final_url=(
            "https://example.com/article"
        ),
    )

    second_source = make_source(
        source_id=202,
        final_url=(
            "HTTPS://EXAMPLE.COM:443/"
            "article#reference"
        ),
    )

    provenance = make_provenance(
        claims=[
            make_claim(
                supporting_sources=[
                    first_source,
                    second_source,
                ],
            )
        ],
    )

    result = build_registry(
        provenance=provenance,
    )

    assert len(result.bibliography) == 1

    assert (
        result.bibliography[0].source_ids
        == [201, 202]
    )

    assert (
        result.sections[0].supporting_numbers
        == [1]
    )


def test_repeated_source_id_not_duplicated():

    source = make_source()

    provenance = make_provenance(
        claims=[
            make_claim(
                supporting_sources=[
                    source,
                    source,
                    source,
                ],
            )
        ],
    )

    result = build_registry(
        provenance=provenance,
    )

    assert len(result.bibliography) == 1

    assert (
        result.bibliography[0].source_ids
        == [201]
    )

    assert (
        result.sections[0].supporting_numbers
        == [1]
    )


def test_source_shared_between_evidence_relationships():

    source = make_source()

    provenance = make_provenance(
        claims=[
            make_claim(
                supporting_sources=[
                    source,
                ],
                contradicting_sources=[
                    source,
                ],
            )
        ],
    )

    result = build_registry(
        provenance=provenance,
    )

    assert len(result.bibliography) == 1

    section = result.sections[0]

    assert section.supporting_numbers == [1]

    assert section.contradicting_numbers == [1]


def test_conflicting_source_urls_rejected():

    first_source = make_source(
        source_id=201,
        final_url=(
            "https://example.com/first"
        ),
    )

    second_source = make_source(
        source_id=201,
        final_url=(
            "https://example.com/second"
        ),
    )

    provenance = make_provenance(
        claims=[
            make_claim(
                supporting_sources=[
                    first_source,
                ],
                contradicting_sources=[
                    second_source,
                ],
            )
        ],
    )

    with pytest.raises(
        ValueError,
        match=(
            "Source ID has conflicting URLs "
            "in citation provenance: 201"
        ),
    ):

        build_registry(
            provenance=provenance,
        )


def test_shared_source_across_sections():

    report = make_report(
        sections=[
            make_section(
                section_id=301,
                ordinal=1,
                claim_ids=[100],
            ),
            make_section(
                section_id=302,
                ordinal=2,
                claim_ids=[200],
            ),
        ],
    )

    source = make_source()

    provenance = make_provenance(
        claims=[
            make_claim(
                claim_id=100,
                supporting_sources=[
                    source
                ],
            ),
            make_claim(
                claim_id=200,
                supporting_sources=[
                    source
                ],
            ),
        ],
    )

    result = build_registry(
        report=report,
        provenance=provenance,
    )

    assert len(result.bibliography) == 1

    assert len(result.sections) == 2

    assert (
        result.sections[0].supporting_numbers
        == [1]
    )

    assert (
        result.sections[1].supporting_numbers
        == [1]
    )


def test_section_order_controls_numbering():

    report = make_report(
        sections=[
            make_section(
                section_id=302,
                ordinal=2,
                claim_ids=[200],
            ),
            make_section(
                section_id=301,
                ordinal=1,
                claim_ids=[100],
            ),
        ],
    )

    provenance = make_provenance(
        claims=[
            make_claim(
                claim_id=200,
                supporting_sources=[
                    make_source(
                        source_id=202,
                    )
                ],
            ),
            make_claim(
                claim_id=100,
                supporting_sources=[
                    make_source(
                        source_id=201,
                    )
                ],
            ),
        ],
    )

    result = build_registry(
        report=report,
        provenance=provenance,
    )

    assert [
        section.section_id
        for section in result.sections
    ] == [
        301,
        302,
    ]

    assert [
        entry.source_ids
        for entry in result.bibliography
    ] == [
        [201],
        [202],
    ]

    assert [
        entry.number
        for entry in result.bibliography
    ] == [
        1,
        2,
    ]


def test_equal_section_ordinals_use_section_id():

    report = make_report(
        sections=[
            make_section(
                section_id=302,
                ordinal=1,
                claim_ids=[100],
            ),
            make_section(
                section_id=301,
                ordinal=1,
                claim_ids=[100],
            ),
        ],
    )

    result = build_registry(
        report=report,
    )

    assert [
        section.section_id
        for section in result.sections
    ] == [
        301,
        302,
    ]


def test_deterministic_registry_without_input_mutation():

    report = make_report()

    provenance = make_provenance(
        claims=[
            make_claim(
                supporting_sources=[
                    make_source(
                        source_id=201,
                    ),
                    make_source(
                        source_id=202,
                    ),
                ],
                contradicting_sources=[
                    make_source(
                        source_id=203,
                    ),
                ],
            )
        ],
    )

    original_report = report.model_dump()

    original_provenance = (
        provenance.model_dump()
    )

    registry = ReportCitationRegistry()

    first_result = registry.build(
        report=report,
        provenance=provenance,
    )

    second_result = registry.build(
        report=report,
        provenance=provenance,
    )

    assert (
        first_result.model_dump()
        == second_result.model_dump()
    )

    assert (
        report.model_dump()
        == original_report
    )

    assert (
        provenance.model_dump()
        == original_provenance
    )


def test_session_mismatch_rejected():

    provenance = make_provenance(
        session_id="foreign-session",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Report and citation provenance "
            "belong to different research sessions."
        ),
    ):

        build_registry(
            provenance=provenance,
        )


def test_duplicate_claim_provenance_rejected():

    provenance = make_provenance(
        claims=[
            make_claim(
                claim_id=100,
            ),
            make_claim(
                claim_id=100,
            ),
        ],
    )

    with pytest.raises(
        ValueError,
        match=(
            "Duplicate reviewed claim in "
            "citation provenance: 100"
        ),
    ):

        build_registry(
            provenance=provenance,
        )


@pytest.mark.parametrize(
    "claim_ids, expected_message",
    [
        (
            [],
            "Missing: [100]. Unexpected: [].",
        ),
        (
            [100, 200],
            "Missing: []. Unexpected: [200].",
        ),
        (
            [200],
            "Missing: [100]. Unexpected: [200].",
        ),
    ],
)
def test_mismatched_claim_provenance_rejected(
    claim_ids,
    expected_message,
):

    provenance = make_provenance(
        claims=[
            make_claim(
                claim_id=claim_id,
            )
            for claim_id in claim_ids
        ],
    )

    with pytest.raises(
        ValueError
    ) as error:

        build_registry(
            provenance=provenance,
        )

    assert expected_message in str(
        error.value
    )


@pytest.mark.parametrize(
    "url, expected_url",
    [
        (
            "HTTPS://EXAMPLE.COM",
            "https://example.com/",
        ),
        (
            "http://example.com:80/article",
            "http://example.com/article",
        ),
        (
            "https://example.com:443/article",
            "https://example.com/article",
        ),
        (
            "https://example.com:8443/article",
            "https://example.com:8443/article",
        ),
        (
            "https://example.com/article#section",
            "https://example.com/article",
        ),
        (
            "https://example.com/article?q=research",
            "https://example.com/article?q=research",
        ),
        (
            "  https://example.com/article  ",
            "https://example.com/article",
        ),
        (
            "http://[2001:db8::1]:80",
            "http://[2001:db8::1]/",
        ),
    ],
)
def test_url_normalization(
    url,
    expected_url,
):

    source = make_source(
        final_url=url,
    )

    provenance = make_provenance(
        claims=[
            make_claim(
                supporting_sources=[
                    source
                ],
            )
        ],
    )

    result = build_registry(
        provenance=provenance,
    )

    assert (
        result.bibliography[0].url
        == expected_url
    )


@pytest.mark.parametrize(
    "url, expected_message",
    [
        (
            "",
            "unsupported URL scheme:",
        ),
        (
            "ftp://example.com/article",
            "unsupported URL scheme:",
        ),
        (
            "file:///research/article.html",
            "unsupported URL scheme:",
        ),
        (
            "https:///article",
            "URL has no hostname:",
        ),
        (
            "https://user@example.com/article",
            "URL contains userinfo.",
        ),
        (
            "https://user:password@example.com/article",
            "URL contains userinfo.",
        ),
        (
            "https://example.com:invalid/article",
            "Port could not be cast",
        ),
        (
            "https://example.com:99999/article",
            "Port out of range",
        ),
    ],
)
def test_invalid_urls_rejected(
    url,
    expected_message,
):

    source = make_source(
        final_url=url,
    )

    provenance = make_provenance(
        claims=[
            make_claim(
                supporting_sources=[
                    source
                ],
            )
        ],
    )

    with pytest.raises(
        ValueError
    ) as error:

        build_registry(
            provenance=provenance,
        )

    assert expected_message in str(
        error.value
    )


def test_distinct_query_strings_not_deduplicated():

    first_source = make_source(
        source_id=201,
        final_url=(
            "https://example.com/article?id=1"
        ),
    )

    second_source = make_source(
        source_id=202,
        final_url=(
            "https://example.com/article?id=2"
        ),
    )

    provenance = make_provenance(
        claims=[
            make_claim(
                supporting_sources=[
                    first_source,
                    second_source,
                ],
            )
        ],
    )

    result = build_registry(
        provenance=provenance,
    )

    assert len(result.bibliography) == 2

    assert (
        result.sections[0].supporting_numbers
        == [1, 2]
    )