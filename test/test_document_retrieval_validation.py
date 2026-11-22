from unittest.mock import patch

import httpx

from domain.web import RetrievedDocument

from extraction.html import (
    HtmlDocumentExtractor,
)

from retrieval.http import (
    HttpDocumentRetriever,
)

from security.url_validator import (
    UrlValidator,
)


TEST_URL = "https://example.com/research"


def retrieve_document(
    status_code: int,
    content: bytes,
    content_type: str,
) -> RetrievedDocument:

    def handle_request(
        request: httpx.Request,
    ) -> httpx.Response:

        assert str(request.url) == TEST_URL

        return httpx.Response(
            status_code=status_code,
            headers={
                "Content-Type": content_type,
            },
            content=content,
        )

    transport = httpx.MockTransport(
        handle_request
    )

    original_client = httpx.Client

    def create_client(
        *args,
        **kwargs,
    ):

        kwargs["transport"] = transport

        return original_client(
            *args,
            **kwargs,
        )

    validator = UrlValidator()

    retriever = HttpDocumentRetriever(
        url_validator=validator,
    )

    with patch.object(
        UrlValidator,
        "validate",
        return_value=None,
    ):

        with patch(
            "retrieval.http.httpx.Client",
            side_effect=create_client,
        ):

            return retriever.retrieve(
                TEST_URL
            )


def expect_empty_response_rejection(
    status_code: int,
):

    try:

        retrieve_document(
            status_code=status_code,
            content=b"",
            content_type="text/html",
        )

    except ValueError as exc:

        assert "no content" in str(exc)

    else:

        raise AssertionError(
            "Empty HTTP response was "
            "unexpectedly accepted."
        )


def extract_document(
    content: str,
    content_type: str,
    status_code: int = 200,
):

    retrieved = RetrievedDocument(
        requested_url=TEST_URL,
        final_url=TEST_URL,
        status_code=status_code,
        content_type=content_type,
        content=content.encode("utf-8"),
    )

    extractor = HtmlDocumentExtractor()

    return extractor.extract(
        retrieved
    )


def main():

    print()
    print("DOCUMENT RETRIEVAL VALIDATION")
    print("=============================")

    html = (
        "<html>"
        "<head>"
        "<title>Test Research Document</title>"
        "</head>"
        "<body>"
        "<p>Deterministic research evidence.</p>"
        "</body>"
        "</html>"
    )

    document = retrieve_document(
        status_code=200,
        content=html.encode("utf-8"),
        content_type="text/html",
    )

    assert document.status_code == 200
    assert document.content

    print(
        "TEST 1 - Valid HTTP 200 accepted: PASSED"
    )

    expect_empty_response_rejection(
        status_code=202
    )

    print(
        "TEST 2 - Empty HTTP 202 rejected: PASSED"
    )

    expect_empty_response_rejection(
        status_code=200
    )

    print(
        "TEST 3 - Empty HTTP 200 rejected: PASSED"
    )

    document = retrieve_document(
        status_code=203,
        content=html.encode("utf-8"),
        content_type="text/html",
    )

    assert document.status_code == 203
    assert document.content

    print(
        "TEST 4 - Valid HTTP 203 accepted: PASSED"
    )

    extracted = extract_document(
        content=html,
        content_type="text/html",
    )

    assert extracted.title == (
        "Test Research Document"
    )

    assert (
        "Deterministic research evidence."
        in extracted.extracted_text
    )

    print(
        "TEST 5 - HTML extraction: PASSED"
    )

    extracted = extract_document(
        content=(
            "<html>"
            "<head></head>"
            "<body></body>"
            "</html>"
        ),
        content_type="text/html",
    )

    assert not extracted.extracted_text.strip()

    print(
        "TEST 6 - Empty HTML extraction: PASSED"
    )

    extracted = extract_document(
        content=" \t\r\n ",
        content_type="text/plain",
    )

    assert not extracted.extracted_text.strip()

    print(
        "TEST 7 - Whitespace extraction: PASSED"
    )

    extracted = extract_document(
        content=html,
        content_type="application/xhtml+xml",
    )

    assert extracted.title == (
        "Test Research Document"
    )

    assert (
        "Deterministic research evidence."
        in extracted.extracted_text
    )

    assert "<p>" not in extracted.extracted_text

    print(
        "TEST 8 - XHTML extraction: PASSED"
    )

    extracted = extract_document(
        content="Deterministic plain-text evidence.",
        content_type="text/plain",
    )

    assert extracted.extracted_text == (
        "Deterministic plain-text evidence."
    )

    print(
        "TEST 9 - Plain-text extraction: PASSED"
    )

    extracted = extract_document(
        content=(
            "<html>"
            "<body>"
            "<p>Evidence without a title.</p>"
            "</body>"
            "</html>"
        ),
        content_type="text/html",
    )

    assert not extracted.title

    assert (
        "Evidence without a title."
        in extracted.extracted_text
    )

    print(
        "TEST 10 - Untitled document accepted: PASSED"
    )

    print()
    print("PASS")


if __name__ == "__main__":

    main()