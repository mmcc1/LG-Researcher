#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

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


class AdminPasswordResetRequestResponse(BaseModel):

    id: str
    user_id: str
    username: str
    status: str
    requested_at: datetime
    reviewed_at: datetime | None
    reviewed_by: str | None


class AdminPasswordResetRequestListResponse(BaseModel):

    items: list[AdminPasswordResetRequestResponse]
    total: int
    limit: int
    offset: int


class AdminPasswordResetActionResponse(BaseModel):

    id: str
    status: str
    message: str


class AdminPasswordResetApprovalResponse(BaseModel):

    id: str
    status: str
    message: str
    temporary_password: str
    

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