import pytest

from domain.report_citation_registry import (
    BibliographyEntry,
    SectionCitationReferences,
    ReportCitationRegistryResult,
)

from processing.report_text_formatter import (
    ReportTextFormatter,
)

from processing.report_citation_registry import (
    ReportCitationRegistry,
)

from test_report_citation_registry_validation import (
    SESSION_ID,
    make_source,
    make_claim,
    make_section,
    make_report,
    make_provenance,
)


def make_bibliography_entry(
    number=1,
    source_id=201,
    title="Test research source",
    url=None,
):

    if url is None:

        url = (
            f"https://example.com/source/{source_id}"
        )

    return BibliographyEntry(
        number=number,
        title=title,
        url=url,
        source_ids=[
            source_id
        ],
    )


def make_section_references(
    section_id=301,
    ordinal=1,
    supporting_numbers=None,
    contradicting_numbers=None,
):

    if supporting_numbers is None:

        supporting_numbers = [1]

    if contradicting_numbers is None:

        contradicting_numbers = []

    return SectionCitationReferences(
        section_id=section_id,
        ordinal=ordinal,
        supporting_numbers=supporting_numbers,
        contradicting_numbers=contradicting_numbers,
    )


def make_registry(
    sections=None,
    bibliography=None,
    session_id=SESSION_ID,
):

    if sections is None:

        sections = [
            make_section_references()
        ]

    if bibliography is None:

        bibliography = [
            make_bibliography_entry()
        ]

    return ReportCitationRegistryResult(
        research_session_id=session_id,
        sections=sections,
        bibliography=bibliography,
    )


def format_report(
    report=None,
    registry=None,
):

    if report is None:

        report = make_report()

    if registry is None:

        registry = make_registry()

    formatter = ReportTextFormatter()

    return formatter.format(
        report=report,
        citation_registry=registry,
    )


def get_section_text(
    report_text,
    heading,
):

    lines = report_text.splitlines()

    heading_index = lines.index(
        heading
    )

    content_start = (
        heading_index + 2
    )

    section_end = len(
        lines
    )

    for index in range(
        content_start,
        len(lines),
    ):

        if lines[index] == "-" * 70:

            section_end = index

            break

    return "\n".join(
        lines[
            content_start:section_end
        ]
    )


def test_complete_report_content_preserved():

    report = make_report()

    report.limitations = [
        "Limited supporting evidence.",
        "Further investigation is required.",
    ]

    report_text = format_report(
        report=report,
    )

    assert report.title in report_text

    assert (
        "EXECUTIVE SUMMARY"
        in report_text
    )

    assert (
        report.executive_summary
        in report_text
    )

    for section in report.sections:

        assert section.heading in report_text

        assert section.content in report_text

    assert "CONCLUSIONS" in report_text

    assert report.conclusions in report_text

    assert "LIMITATIONS" in report_text

    for limitation in report.limitations:

        assert (
            f"- {limitation}"
            in report_text
        )

    assert "BIBLIOGRAPHY" in report_text

    assert (
        "Reviewed claim IDs:"
        not in report_text
    )


def test_supporting_references_formatted():

    registry = make_registry(
        sections=[
            make_section_references(
                supporting_numbers=[
                    1,
                    2,
                ],
            )
        ],
        bibliography=[
            make_bibliography_entry(
                number=1,
                source_id=201,
            ),
            make_bibliography_entry(
                number=2,
                source_id=202,
            ),
        ],
    )

    report_text = format_report(
        registry=registry,
    )

    assert (
        "Sources cited: [1], [2]"
        in report_text
    )

    assert (
        "Contradicting evidence:"
        not in report_text
    )


def test_contradicting_references_formatted():

    registry = make_registry(
        sections=[
            make_section_references(
                supporting_numbers=[1],
                contradicting_numbers=[2, 3],
            )
        ],
        bibliography=[
            make_bibliography_entry(
                number=1,
                source_id=201,
            ),
            make_bibliography_entry(
                number=2,
                source_id=202,
            ),
            make_bibliography_entry(
                number=3,
                source_id=203,
            ),
        ],
    )

    report_text = format_report(
        registry=registry,
    )

    assert (
        "Sources cited: [1]"
        in report_text
    )

    assert (
        "Contradicting evidence: [2], [3]"
        in report_text
    )


def test_bibliography_entries_formatted():

    registry = make_registry(
        bibliography=[
            make_bibliography_entry(
                number=1,
                source_id=201,
                title="First publication",
            ),
            make_bibliography_entry(
                number=2,
                source_id=202,
                title="Second publication",
            ),
        ],
        sections=[
            make_section_references(
                supporting_numbers=[1, 2],
            )
        ],
    )

    report_text = format_report(
        registry=registry,
    )

    bibliography_text = report_text.split(
        "BIBLIOGRAPHY",
        1,
    )[1]

    for entry in registry.bibliography:

        expected_text = (
            f"[{entry.number}] {entry.title}\n"
            f"{entry.url}"
        )

        assert expected_text in bibliography_text

        assert (
            bibliography_text.count(
                expected_text
            )
            == 1
        )


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
def test_untitled_source_formatted(
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

    report = make_report()

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

    registry = ReportCitationRegistry().build(
        report=report,
        provenance=provenance,
    )

    report_text = format_report(
        report=report,
        registry=registry,
    )

    entry = next(
        entry
        for entry in registry.bibliography
        if source.source_id in entry.source_ids
    )

    assert entry.title == expected_url

    assert entry.url == expected_url

    expected_bibliography_text = (
        f"[{entry.number}] {expected_url}\n"
        f"{expected_url}"
    )

    assert (
        expected_bibliography_text
        in report_text
    )

    if relationship == "supporting":

        expected_reference = (
            f"Sources cited: [{entry.number}]"
        )

    else:

        expected_reference = (
            "Contradicting evidence: "
            f"[{entry.number}]"
        )

    assert expected_reference in report_text


def test_shared_bibliography_entry_across_sections():

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

    registry = ReportCitationRegistry().build(
        report=report,
        provenance=provenance,
    )

    report_text = format_report(
        report=report,
        registry=registry,
    )

    assert len(
        registry.bibliography
    ) == 1

    for section in report.sections:

        section_text = get_section_text(
            report_text=report_text,
            heading=section.heading,
        )

        assert (
            "Sources cited: [1]"
            in section_text
        )

    bibliography_text = report_text.split(
        "BIBLIOGRAPHY",
        1,
    )[1]

    assert (
        bibliography_text.count(
            f"[1] {source.title}"
        )
        == 1
    )


def test_same_source_supporting_and_contradicting():

    registry = make_registry(
        sections=[
            make_section_references(
                supporting_numbers=[1],
                contradicting_numbers=[1],
            )
        ],
    )

    report_text = format_report(
        registry=registry,
    )

    assert (
        "Sources cited: [1]"
        in report_text
    )

    assert (
        "Contradicting evidence: [1]"
        in report_text
    )

    bibliography_text = report_text.split(
        "BIBLIOGRAPHY",
        1,
    )[1]

    assert (
        bibliography_text.count(
            "[1] Test research source"
        )
        == 1
    )


def test_section_without_citations():

    report = make_report(
        sections=[
            make_section(
                claim_ids=[],
            )
        ],
    )

    registry = make_registry(
        sections=[
            make_section_references(
                supporting_numbers=[],
                contradicting_numbers=[],
            )
        ],
        bibliography=[],
    )

    report_text = format_report(
        report=report,
        registry=registry,
    )

    assert (
        "Sources cited: None"
        in report_text
    )

    assert (
        "Contradicting evidence:"
        not in report_text
    )

    assert "BIBLIOGRAPHY" in report_text


def test_empty_report_sections_and_bibliography():

    report = make_report(
        sections=[],
    )

    registry = make_registry(
        sections=[],
        bibliography=[],
    )

    report_text = format_report(
        report=report,
        registry=registry,
    )

    assert report.title in report_text

    assert (
        "EXECUTIVE SUMMARY"
        in report_text
    )

    assert "CONCLUSIONS" in report_text

    assert "LIMITATIONS" in report_text

    assert "BIBLIOGRAPHY" in report_text

    assert (
        "Sources cited:"
        not in report_text
    )


def test_citations_associated_with_correct_sections():

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

    registry = make_registry(
        sections=[
            make_section_references(
                section_id=302,
                ordinal=2,
                supporting_numbers=[2],
            ),
            make_section_references(
                section_id=301,
                ordinal=1,
                supporting_numbers=[1],
            ),
        ],
        bibliography=[
            make_bibliography_entry(
                number=1,
                source_id=201,
            ),
            make_bibliography_entry(
                number=2,
                source_id=202,
            ),
        ],
    )

    report_text = format_report(
        report=report,
        registry=registry,
    )

    first_section_text = get_section_text(
        report_text=report_text,
        heading=report.sections[0].heading,
    )

    second_section_text = get_section_text(
        report_text=report_text,
        heading=report.sections[1].heading,
    )

    assert (
        "Sources cited: [1]"
        in first_section_text
    )

    assert (
        "Sources cited: [2]"
        not in first_section_text
    )

    assert (
        "Sources cited: [2]"
        in second_section_text
    )

    assert (
        "Sources cited: [1]"
        not in second_section_text
    )


def test_unicode_content_preserved():

    report = make_report()

    report.title = (
        "International research — Étude scientifique"
    )

    report.executive_summary = (
        "科学研究 — Δοκιμή"
    )

    report.sections[0].heading = (
        "神経科学 — Neuroscience"
    )

    report.sections[0].content = (
        "Unicode research content: "
        "研究、ข้อมูล、café、α + β."
    )

    report.conclusions = (
        "Résultats de la recherche."
    )

    report.limitations = [
        "Données limitées — 数据有限"
    ]

    source_title = (
        "神経科学 — Étude clinique"
    )

    registry = make_registry(
        bibliography=[
            make_bibliography_entry(
                title=source_title,
            )
        ],
    )

    report_text = format_report(
        report=report,
        registry=registry,
    )

    assert report.title in report_text

    assert (
        report.executive_summary
        in report_text
    )

    assert (
        report.sections[0].heading
        in report_text
    )

    assert (
        report.sections[0].content
        in report_text
    )

    assert report.conclusions in report_text

    assert (
        report.limitations[0]
        in report_text
    )

    assert source_title in report_text

    encoded_text = report_text.encode(
        "utf-8"
    )

    decoded_text = encoded_text.decode(
        "utf-8"
    )

    assert decoded_text == report_text


def test_deterministic_formatting_without_input_mutation():

    report = make_report()

    registry = make_registry()

    original_report = report.model_dump()

    original_registry = registry.model_dump()

    formatter = ReportTextFormatter()

    first_result = formatter.format(
        report=report,
        citation_registry=registry,
    )

    second_result = formatter.format(
        report=report,
        citation_registry=registry,
    )

    assert first_result == second_result

    assert (
        report.model_dump()
        == original_report
    )

    assert (
        registry.model_dump()
        == original_registry
    )


def test_session_mismatch_rejected():

    registry = make_registry(
        session_id="foreign-session",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Report and citation registry "
            "belong to different research sessions."
        ),
    ):

        format_report(
            registry=registry,
        )


def test_duplicate_section_references_rejected():

    registry = make_registry(
        sections=[
            make_section_references(),
            make_section_references(),
        ],
    )

    with pytest.raises(
        ValueError,
        match=(
            "Duplicate citation references "
            "for report section: 301"
        ),
    ):

        format_report(
            registry=registry,
        )


@pytest.mark.parametrize(
    "section_ids",
    [
        [],
        [301, 302],
        [302],
    ],
)
def test_mismatched_section_references_rejected(
    section_ids,
):

    registry = make_registry(
        sections=[
            make_section_references(
                section_id=section_id,
            )
            for section_id in section_ids
        ],
    )

    with pytest.raises(
        ValueError,
        match=(
            "Citation registry sections do not "
            "match the persisted report sections."
        ),
    ):

        format_report(
            registry=registry,
        )


@pytest.mark.parametrize(
    "numbers",
    [
        [0],
        [-1],
        [2],
        [1, 1],
        [1, 3],
        [2, 1],
    ],
)
def test_invalid_bibliography_numbering_rejected(
    numbers,
):

    bibliography = []

    for index, number in enumerate(
        numbers
    ):

        entry = make_bibliography_entry(
            number=number,
            source_id=201 + index,
        )

        bibliography.append(
            entry
        )

    registry = make_registry(
        bibliography=bibliography,
    )

    with pytest.raises(
        ValueError,
        match=(
            "Bibliography numbering is invalid."
        ),
    ):

        format_report(
            registry=registry,
        )


@pytest.mark.parametrize(
    "reference",
    [
        0,
        -1,
        2,
        999,
    ],
)
@pytest.mark.parametrize(
    "relationship",
    [
        "supporting",
        "contradicting",
    ],
)
def test_unknown_bibliography_reference_rejected(
    reference,
    relationship,
):

    supporting_numbers = [1]

    contradicting_numbers = []

    if relationship == "supporting":

        supporting_numbers.append(
            reference
        )

    else:

        contradicting_numbers.append(
            reference
        )

    registry = make_registry(
        sections=[
            make_section_references(
                supporting_numbers=supporting_numbers,
                contradicting_numbers=contradicting_numbers,
            )
        ],
    )

    with pytest.raises(
        ValueError,
        match=(
            "Section contains an unknown "
            "bibliography reference."
        ),
    ):

        format_report(
            registry=registry,
        )


def test_reference_to_empty_bibliography_rejected():

    registry = make_registry(
        sections=[
            make_section_references(
                supporting_numbers=[1],
            )
        ],
        bibliography=[],
    )

    with pytest.raises(
        ValueError,
        match=(
            "Section contains an unknown "
            "bibliography reference."
        ),
    ):

        format_report(
            registry=registry,
        )