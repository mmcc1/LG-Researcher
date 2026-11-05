from pydantic import BaseModel


class RetrievedDocument(BaseModel):

    requested_url: str

    final_url: str

    status_code: int

    content_type: str

    content: bytes