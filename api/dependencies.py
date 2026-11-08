
import os

from collections.abc import Generator

from fastapi import (
    Depends,
    HTTPException,
    Request,
    status,
)

from sqlalchemy import select
from sqlalchemy.orm import Session

from application.authentication_service import utc_now

from persistence.database import SessionLocal

from persistence.models import (
    UserAccount,
    UserSession,
)

from security.session_tokens import (
    hash_token,
    verify_token,
)



def get_db() -> Generator[Session, None, None]:

    with SessionLocal() as db:

        yield db



SESSION_COOKIE_NAME = "lg_researcher_session"

SAFE_METHODS = {
    "GET",
    "HEAD",
    "OPTIONS",
}


def get_authenticated_session(
    request: Request,
    db: Session = Depends(get_db),
) -> tuple[UserAccount, UserSession]:

    token = request.cookies.get(
        SESSION_COOKIE_NAME
    )

    if not token:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash
            == hash_token(token)
        )
    )

    now = utc_now()

    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
    ):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired.",
        )

    user = db.get(
        UserAccount,
        session.user_id,
    )

    if (
        user is None
        or not user.is_active
        or user.approval_status != "approved"
    ):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is not available.",
        )

    if request.method.upper() not in SAFE_METHODS:

        validate_request_origin(request)

        supplied_csrf = request.headers.get(
            "X-CSRF-Token",
            "",
        )

        if (
            not supplied_csrf
            or not verify_token(
                supplied_csrf,
                session.csrf_token_hash,
            )
        ):

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token.",
            )

    return user, session


def validate_request_origin(
    request: Request,
) -> None:

    origin = request.headers.get(
        "Origin"
    )

    configured_origins = os.environ.get(
        "LG_RESEARCHER_ALLOWED_ORIGINS",
        "",
    )

    allowed_origins = {
        value.strip()
        for value in configured_origins.split(",")
        if value.strip()
    }

    if not allowed_origins:

        expected_origin = (
            f"{request.url.scheme}://"
            f"{request.url.netloc}"
        )

        allowed_origins.add(
            expected_origin
        )

    if origin not in allowed_origins:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid request origin.",
        )


def get_current_user(
    authentication: tuple[
        UserAccount,
        UserSession,
    ] = Depends(get_authenticated_session),
) -> UserAccount:

    user, session = authentication

    return user


def get_current_user_id(
    user: UserAccount = Depends(get_current_user),
) -> str:

    if user.must_change_password:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required.",
        )

    return user.id



def require_admin(
    user: UserAccount = Depends(get_current_user),
) -> UserAccount:

    if user.must_change_password:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required.",
        )

    if user.role != "admin":

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )

    return user

