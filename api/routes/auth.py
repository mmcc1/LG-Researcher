
import os

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from sqlalchemy.orm import Session

from api.dependencies import (
    SESSION_COOKIE_NAME,
    get_authenticated_session,
    get_db,
    validate_request_origin,
)

from api.schemas.auth import (
    ChangePasswordRequest,
    CurrentSessionResponse,
    CurrentUserResponse,
    LoginRequest,
    LoginResponse,
    MessageResponse,
)

from application.authentication_service import (
    AuthenticationError,
    AuthenticationService,
)

from persistence.models import (
    UserAccount,
    UserSession,
)

from security.session_tokens import (
    generate_token,
    hash_token,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


def build_user_response(
    user: UserAccount,
) -> CurrentUserResponse:

    return CurrentUserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        must_change_password=(
            user.must_change_password
        ),
    )


def set_session_cookie(
    response: Response,
    token: str,
) -> None:

    environment = os.environ.get(
        "LG_RESEARCHER_API_ENV",
        "",
    ).strip()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=environment != "development",
        samesite="strict",
        path="/api",
        max_age=12 * 60 * 60,
    )


def clear_session_cookie(
    response: Response,
) -> None:

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/api",
        secure=(
            os.environ.get(
                "LG_RESEARCHER_API_ENV",
                "",
            ).strip() != "development"
        ),
        httponly=True,
        samesite="strict",
    )


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    request: Request,
    credentials: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):

    validate_request_origin(request)

    service = AuthenticationService(
        db
    )

    try:

        user = service.authenticate(
            username=credentials.username,
            password=credentials.password,
        )

    except AuthenticationError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or unavailable account.",
        )

    created = service.create_session(
        user
    )

    set_session_cookie(
        response,
        created.session_token,
    )

    response.headers["Cache-Control"] = (
        "no-store"
    )

    return LoginResponse(
        user=build_user_response(user),
        csrf_token=created.csrf_token,
        expires_at=created.expires_at,
    )


@router.get(
    "/me",
    response_model=CurrentSessionResponse,
)
def current_session(
    response: Response,
    authentication: tuple[
        UserAccount,
        UserSession,
    ] = Depends(get_authenticated_session),
    db: Session = Depends(get_db),
):

    user, session = authentication

    csrf_token = generate_token()

    session.csrf_token_hash = hash_token(
        csrf_token
    )

    db.commit()

    response.headers["Cache-Control"] = (
        "no-store"
    )

    return CurrentSessionResponse(
        user=build_user_response(user),
        csrf_token=csrf_token,
        expires_at=session.expires_at,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
def logout(
    response: Response,
    authentication: tuple[
        UserAccount,
        UserSession,
    ] = Depends(get_authenticated_session),
    db: Session = Depends(get_db),
):

    user, session = authentication

    service = AuthenticationService(
        db
    )

    service.revoke_session(
        session
    )

    clear_session_cookie(
        response
    )

    response.headers["Cache-Control"] = (
        "no-store"
    )

    return None


@router.post(
    "/change-password",
    response_model=MessageResponse,
)
def change_password(
    request: ChangePasswordRequest,
    response: Response,
    authentication: tuple[
        UserAccount,
        UserSession,
    ] = Depends(get_authenticated_session),
    db: Session = Depends(get_db),
):

    user, session = authentication

    service = AuthenticationService(
        db
    )

    try:

        service.change_password(
            user=user,
            current_password=(
                request.current_password
            ),
            new_password=(
                request.new_password
            ),
        )

    except AuthenticationError as exc:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    clear_session_cookie(
        response
    )

    response.headers["Cache-Control"] = (
        "no-store"
    )

    return MessageResponse(
        message=(
            "Password changed successfully. "
            "Please log in again."
        )
    )
