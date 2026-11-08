
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import (
    select,
    update,
)

from sqlalchemy.orm import Session

from persistence.models import (
    UserAccount,
    UserSession,
)

from security.password_hasher import (
    hash_password,
    verify_password,
)

from security.session_tokens import (
    generate_token,
    hash_token,
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


class AuthenticationService:

    def __init__(
        self,
        db: Session,
    ):

        self.db = db

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
