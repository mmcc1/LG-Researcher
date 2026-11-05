import httpx

from domain.web import RetrievedDocument
from retrieval.base import DocumentRetriever
from security.url_validator import UrlValidator


class HttpDocumentRetriever(DocumentRetriever):

    ALLOWED_CONTENT_TYPES = {
        "text/html",
        "text/plain",
        "application/xhtml+xml",
    }

    def __init__(
        self,
        url_validator: UrlValidator,
        timeout_seconds: float = 10.0,
        max_content_bytes: int = 5_000_000,
        max_redirects: int = 5,
    ):
        self.url_validator = url_validator
        self.timeout_seconds = timeout_seconds
        self.max_content_bytes = max_content_bytes
        self.max_redirects = max_redirects

    def retrieve(
    self,
    url: str,
) -> RetrievedDocument:
        
        current_url = url
        
        with httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=False,
            headers={
                "User-Agent":
                "Researcher/0.1"
        },
        ) as client:

            for _ in range(
                self.max_redirects + 1
            ):

                self.url_validator.validate(
                    current_url
                )

                with client.stream(
                    "GET",
                    current_url,
                ) as response:

                    if response.is_redirect:

                        location = (
                            response.headers.get(
                                "location"
                            )
                        )

                        if not location:
                            raise ValueError(
                                "Redirect response "
                                "contains no Location header."
                            )

                        current_url = str(
                            response.url.join(
                                location
                            )
                        )

                        continue

                    response.raise_for_status()

                    content_type = (
                        response.headers
                        .get("content-type", "")
                        .split(";")[0]
                        .strip()
                        .lower()
                    )

                    if (
                        content_type
                        not in self.ALLOWED_CONTENT_TYPES
                    ):
                        raise ValueError(
                            "Unsupported content type: "
                            f"{content_type}"
                        )

                    content_length = (
                        response.headers.get(
                            "content-length"
                        )
                    )

                    if content_length is not None:

                        if (
                            int(content_length)
                            > self.max_content_bytes
                        ):
                            raise ValueError(
                                "Retrieved document exceeds "
                                "maximum permitted size."
                            )

                    content = bytearray()

                    for chunk in response.iter_bytes():

                        content.extend(chunk)

                        if (
                            len(content)
                            > self.max_content_bytes
                        ):
                            raise ValueError(
                                "Retrieved document exceeds "
                                "maximum permitted size."
                            )

                    return RetrievedDocument(
                        requested_url=url,
                        final_url=str(
                            response.url
                        ),
                        status_code=(
                            response.status_code
                        ),
                        content_type=content_type,
                        content=bytes(content),
                    )

        raise ValueError(
            "Maximum redirect count exceeded."
        )