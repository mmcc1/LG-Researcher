from pydantic import BaseModel


class SourceDocument(BaseModel):

    requested_url: str

    final_url: str

    title: str

    content_type: str

    status_code: int

    content_hash: str

    raw_content: str

    extracted_text: str