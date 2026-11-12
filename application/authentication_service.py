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

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import (
    select,
    update,
)

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError


from security.password_hasher import (
    hash_password,
    verify_password,
)

from security.session_tokens import (
    generate_token,
    hash_token,
)

import secrets

from sqlalchemy.exc import IntegrityError

from persistence.models import (
    PasswordResetRequest,
    UserAccount,
    UserSession,
)


SESSION_DURATION_HOURS = 12


def utc_now() -> datetime:

    return datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )


@dataclass(frozen=True)
class CreatedSession:

    session_token: str
    csrf_token: str
    expires_at: datetime


class AuthenticationError(Exception):
    pass

class RegistrationError(Exception):
    pass

class PasswordResetError(Exception):
    pass


class AuthenticationService:

    def __init__(
        self,
        db: Session,
    ):

        self.db = db

    def register_user(
        self,
        username: str,
        password: str,
    ) -> UserAccount:

        normalized_username = username.strip()

        if not normalized_username:

            raise RegistrationError(
                "Username is required."
            )

        if len(normalized_username) > 100:

            raise RegistrationError(
                "Username must not exceed 100 characters."
            )

        if len(password) < 12:

            raise RegistrationError(
                "Password must contain at least 12 characters."
            )

        if len(password) > 1024:

            raise RegistrationError(
                "Password must not exceed 1024 characters."
            )

        existing_user = self.db.scalar(
            select(UserAccount).where(
                UserAccount.username == normalized_username
            )
        )

        if existing_user is not None:

            raise RegistrationError(
                "Username is already registered."
            )

        now = utc_now()

        user = UserAccount(
            id=str(uuid4()),
            username=normalized_username,
            email=None,
            password_hash=hash_password(
                password
            ),
            is_active=False,
            role="user",
            approval_status="pending",
            must_change_password=False,
            approved_at=None,
            email_reports_enabled=False,
            created_at=now,
            last_login_at=None,
        )

        try:

            self.db.add(user)

            self.db.commit()

        except IntegrityError:

            self.db.rollback()

            raise RegistrationError(
                "Username is already registered."
            )

        return user


    def request_password_reset(
        self,
        username: str,
    ) -> None:

        normalized_username = username.strip()

        if not normalized_username:
            return

        user = self.db.scalar(
            select(UserAccount).where(
                UserAccount.username
                == normalized_username
            )
        )

        if user is None:
            return

        if (
            not user.is_active
            or user.approval_status != "approved"
        ):
            return

        existing_request = self.db.scalar(
            select(PasswordResetRequest).where(
                PasswordResetRequest.user_id == user.id,
                PasswordResetRequest.status == "pending",
            )
        )

        if existing_request is not None:
            return

        reset_request = PasswordResetRequest(
            id=str(uuid4()),
            user_id=user.id,
            status="pending",
            requested_at=utc_now(),
            reviewed_at=None,
            reviewed_by=None,
            recovery_code_hash=None,
            recovery_code_expires_at=None,
            completed_at=None,
            failed_attempts=0,
        )

        try:

            self.db.add(reset_request)

            self.db.commit()

        except IntegrityError:

            self.db.rollback()

            # A concurrent request may already have
            # created the pending record.
            return


    def approve_password_reset(
        self,
        reset_request: PasswordResetRequest,
        admin: UserAccount,
    ) -> str:

        if reset_request.status != "pending":

            raise PasswordResetError(
                "Password reset request is no longer pending."
            )

        user = self.db.get(
            UserAccount,
            reset_request.user_id,
        )

        if user is None:

            raise PasswordResetError(
                "User account was not found."
            )

        if (
            not user.is_active
            or user.approval_status != "approved"
        ):

            raise PasswordResetError(
                "User account is not available."
            )

        now = utc_now()

        temporary_password = secrets.token_urlsafe(
            24
        )

        result = self.db.execute(
            update(PasswordResetRequest)
            .where(
                PasswordResetRequest.id == reset_request.id,
                PasswordResetRequest.status == "pending",
            )
            .values(
                status="completed",
                reviewed_at=now,
                reviewed_by=admin.id,
                completed_at=now,
            )
            .execution_options(
                synchronize_session=False
            )
        )

        if result.rowcount != 1:

            self.db.rollback()

            raise PasswordResetError(
                "Password reset request is no longer pending."
            )

        user.password_hash = hash_password(
            temporary_password
        )

        user.must_change_password = True

        self.db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user.id,
                UserSession.revoked_at.is_(None),
            )
            .values(
                revoked_at=now
            )
        )

        # The caller must record the administrator
        # audit event and commit this transaction.
        return temporary_password 


    def reject_password_reset(
        self,
        reset_request: PasswordResetRequest,
        admin: UserAccount,
    ) -> None:

        if reset_request.status != "pending":

            raise PasswordResetError(
                "Password reset request is no longer pending."
            )

        now = utc_now()

        result = self.db.execute(
            update(PasswordResetRequest)
            .where(
                PasswordResetRequest.id == reset_request.id,
                PasswordResetRequest.status == "pending",
            )
            .values(
                status="rejected",
                reviewed_at=now,
                reviewed_by=admin.id,
            )
            .execution_options(
                synchronize_session=False
            )
        )

        if result.rowcount != 1:

            self.db.rollback()

            raise PasswordResetError(
                "Password reset request is no longer pending."
            )

        # The administrator endpoint records the
        # audit event and commits the transaction.


    def authenticate(
        self,
        username: str,
        password: str,
    ) -> UserAccount:

        normalized_username = username.strip()

        user = self.db.scalar(
            select(UserAccount).where(
                UserAccount.username
                == normalized_username
            )
        )

        if user is None:

            raise AuthenticationError(
                "Invalid username or password."
            )

        if not verify_password(
            password,
            user.password_hash,
        ):

            raise AuthenticationError(
                "Invalid username or password."
            )

        if (
            not user.is_active
            or user.approval_status != "approved"
        ):

            raise AuthenticationError(
                "Account is not available."
            )

        return user

    def create_session(
        self,
        user: UserAccount,
    ) -> CreatedSession:

        now = utc_now()

        session_token = generate_token()
        csrf_token = generate_token()

        expires_at = now + timedelta(
            hours=SESSION_DURATION_HOURS
        )

        session = UserSession(
            id=str(uuid4()),
            user_id=user.id,
            token_hash=hash_token(
                session_token
            ),
            csrf_token_hash=hash_token(
                csrf_token
            ),
            created_at=now,
            expires_at=expires_at,
            last_seen_at=now,
            revoked_at=None,
        )

        self.db.add(session)

        user.last_login_at = now

        self.db.commit()

        return CreatedSession(
            session_token=session_token,
            csrf_token=csrf_token,
            expires_at=expires_at,
        )

    def revoke_session(
        self,
        session: UserSession,
    ) -> None:

        session.revoked_at = utc_now()

        self.db.commit()

    def change_password(
        self,
        user: UserAccount,
        current_password: str,
        new_password: str,
    ) -> None:

        if not verify_password(
            current_password,
            user.password_hash,
        ):

            raise AuthenticationError(
                "Current password is incorrect."
            )

        if len(new_password) < 12:

            raise AuthenticationError(
                "New password must contain "
                "at least 12 characters."
            )

        if new_password == current_password:

            raise AuthenticationError(
                "New password must differ "
                "from the current password."
            )

        now = utc_now()

        user.password_hash = hash_password(
            new_password
        )

        user.must_change_password = False

        self.db.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user.id,
                UserSession.revoked_at.is_(None),
            )
            .values(
                revoked_at=now
            )
        )

        self.db.commit()
