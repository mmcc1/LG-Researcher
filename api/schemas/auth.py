
from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
)


class LoginRequest(BaseModel):

    username: str = Field(
        min_length=1,
        max_length=100,
    )

    password: str


class CurrentUserResponse(BaseModel):

    id: str
    username: str
    role: str
    must_change_password: bool


class LoginResponse(BaseModel):

    user: CurrentUserResponse
    csrf_token: str
    expires_at: datetime


class CurrentSessionResponse(BaseModel):

    user: CurrentUserResponse
    csrf_token: str
    expires_at: datetime


class ChangePasswordRequest(BaseModel):

    current_password: str

    new_password: str = Field(
        min_length=12,
        max_length=1024,
    )


class MessageResponse(BaseModel):

    message: str
