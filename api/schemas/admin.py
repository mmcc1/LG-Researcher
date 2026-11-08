
from datetime import datetime

from pydantic import BaseModel


class AdminUserResponse(BaseModel):

    id: str
    username: str
    email: str | None
    role: str
    is_active: bool
    approval_status: str
    must_change_password: bool
    created_at: datetime
    approved_at: datetime | None
    last_login_at: datetime | None


class AdminUserListResponse(BaseModel):

    items: list[AdminUserResponse]
    total: int
    limit: int
    offset: int


class AdminActionResponse(BaseModel):

    id: str
    approval_status: str
    message: str


class AdminResearchJobResponse(BaseModel):

    id: str
    user_id: str
    username: str
    topic: str
    scope: str | None
    status: str
    research_session_id: str | None
    created_at: datetime
    submitted_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    last_error: str | None
    execution_owner: str | None
    lease_expires_at: datetime | None


class AdminResearchJobListResponse(BaseModel):

    items: list[AdminResearchJobResponse]
    total: int
    limit: int
    offset: int


class AdminResearchJobStatusCount(BaseModel):

    status: str
    count: int


class AdminResearchJobSummaryResponse(BaseModel):

    total: int
    statuses: list[AdminResearchJobStatusCount]