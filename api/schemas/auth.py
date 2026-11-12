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

from pydantic import (
    BaseModel,
    Field,
)


class RegisterRequest(BaseModel):

    username: str = Field(
        min_length=1,
        max_length=100,
    )

    password: str = Field(
        min_length=12,
        max_length=1024,
    )

    confirm_password: str = Field(
        min_length=12,
        max_length=1024,
    )


class RegisterResponse(BaseModel):

    message: str


class PasswordResetRequestInput(BaseModel):

    username: str = Field(
        min_length=1,
        max_length=100,
    )


class PasswordResetRequestResponse(BaseModel):

    message: str

    
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
