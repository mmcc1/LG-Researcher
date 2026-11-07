
import os

from collections.abc import Generator

from fastapi import (
    Depends,
    HTTPException,
    status,
)

from sqlalchemy.orm import Session

from persistence.database import (
    SessionLocal,
)

from persistence.models import (
    UserAccount,
)


def get_db() -> Generator[Session, None, None]:

    with SessionLocal() as db:

        yield db


def get_current_user_id(
    db: Session = Depends(get_db),
) -> str:

    environment = os.environ.get(
        "LG_RESEARCHER_API_ENV",
        "",
    ).strip()

    if environment != "development":

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "API authentication is not configured."
            ),
        )

    user_id = os.environ.get(
        "LG_RESEARCHER_DEV_USER_ID",
        "",
    ).strip()

    if not user_id:

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Development user identity is not configured."
            ),
        )

    user = db.get(
        UserAccount,
        user_id,
    )

    if (
        user is None
        or not user.is_active
    ):

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "The configured development user "
                "is not active or does not exist."
            ),
        )

    return user.id
