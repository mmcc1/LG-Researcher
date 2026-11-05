from bs4 import BeautifulSoup
from security.content_hash import calculate_sha256
from domain.source import SourceDocument
from domain.web import RetrievedDocument


class HtmlDocumentExtractor:

    def extract(
        self,
        document: RetrievedDocument,
    ) -> SourceDocument:

        raw_content = document.content.decode(
            "utf-8",
            errors="replace",
        )

        if document.content_type == "text/html":

            soup = BeautifulSoup(
                raw_content,
                "html.parser",
            )

            #
            # Get title before removing elements.
            #

            title = ""

            if soup.title:
                title = soup.title.get_text(
                    " ",
                    strip=True,
                )

            #
            # Remove content that isn't useful
            # research text.
            #

            for element in soup(
                [
                    "script",
                    "style",
                    "noscript",
                    "svg",
                ]
            ):
                element.decompose()

            extracted_text = soup.get_text(
                "\n",
                strip=True,
            )

        else:

            title = ""

            extracted_text = raw_content.strip()

        return SourceDocument(
            requested_url=document.requested_url,
            final_url=document.final_url,
            title=title,
            content_type=document.content_type,
            status_code=document.status_code,
            content_hash=calculate_sha256(
                document.content
            ),
            raw_content=raw_content,
            extracted_text=extracted_text,
        )