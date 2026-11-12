
from collections.abc import Generator
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient

from sqlalchemy import (
    func,
    select,
    text,
)

from persistence.database import (
    engine,
    SessionLocal,
)

from persistence.models import (
    ResearchJob,
    UserAccount,
    UserSession,
)

from api.main import app

from security.password_hasher import hash_password
from security.session_tokens import hash_token

from datetime import timedelta

from security.password_hasher import verify_password


BASE_URL = "https://127.0.0.1:8000"

SESSION_COOKIE_NAME = "lg_researcher_session"

TEST_PASSWORD = "AuthenticationTestPassword123!"


def utc_now() -> datetime:

    return datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )


class AuthenticationTestEnvironment:

    def __init__(self):

        self.user_ids: list[str] = []

        self.clients: list[TestClient] = []

    def create_user(
        self,
        role: str = "user",
        approval_status: str = "approved",
        is_active: bool = True,
        must_change_password: bool = False,
    ) -> tuple[str, str]:

        user_id = str(uuid4())

        username = (
            "auth_test_"
            + user_id.replace("-", "")
        )

        now = utc_now()

        user = UserAccount(
            id=user_id,
            username=username,
            email=None,
            password_hash=hash_password(
                TEST_PASSWORD
            ),
            is_active=is_active,
            role=role,
            approval_status=approval_status,
            must_change_password=(
                must_change_password
            ),
            approved_at=(
                now
                if approval_status == "approved"
                else None
            ),
            email_reports_enabled=False,
            created_at=now,
            last_login_at=None,
        )

        with SessionLocal() as db:

            db.add(user)

            db.commit()

        self.user_ids.append(
            user_id
        )

        return user_id, username

    def create_client(self) -> TestClient:

        client = TestClient(
            app,
            base_url=BASE_URL,
        )

        self.clients.append(
            client
        )

        return client

    def cleanup(self) -> None:

        for client in self.clients:

            client.close()

        if not self.user_ids:

            return

        with SessionLocal() as db:

            sessions = db.scalars(
                select(UserSession).where(
                    UserSession.user_id.in_(
                        self.user_ids
                    )
                )
            ).all()

            for session in sessions:

                db.delete(session)

            db.flush()

            users = db.scalars(
                select(UserAccount).where(
                    UserAccount.id.in_(
                        self.user_ids
                    )
                )
            ).all()

            for user in users:

                db.delete(user)

            db.commit()


@pytest.fixture
def environment() -> Generator[
    AuthenticationTestEnvironment,
    None,
    None,
]:

    with engine.connect() as connection:

        database_name = connection.execute(
            text("SELECT DB_NAME()")
        ).scalar_one()

    if database_name != "Researcher":

        pytest.fail(
            "Refusing to run authentication tests "
            f"against database '{database_name}'."
        )

    environment = AuthenticationTestEnvironment()

    try:

        yield environment

    finally:

        environment.cleanup()


def login(
    client: TestClient,
    username: str,
) -> tuple[str, str]:

    response = client.post(
        "/api/auth/login",
        json={
            "username": username,
            "password": TEST_PASSWORD,
        },
        headers={
            "Origin": BASE_URL,
        },
    )

    assert response.status_code == 200, (
        response.text
    )

    session_token = client.cookies.get(
        SESSION_COOKIE_NAME
    )

    assert session_token is not None

    csrf_token = response.json()[
        "csrf_token"
    ]

    return session_token, csrf_token


def request_as_user(
    client: TestClient,
    method: str,
    path: str,
    csrf_token: str | None = None,
    json_body: dict | None = None,
    origin: str | None = BASE_URL,
):

    headers = {}

    if origin is not None:

        headers["Origin"] = origin

    if csrf_token is not None:

        headers["X-CSRF-Token"] = csrf_token

    options = {
        "headers": headers,
    }

    if json_body is not None:

        options["json"] = json_body

    return client.request(
        method,
        path,
        **options,
    )


def assert_status(
    response,
    expected_status: int,
) -> None:

    assert response.status_code == expected_status, (
        f"Expected HTTP {expected_status}, "
        f"received HTTP {response.status_code}: "
        f"{response.text}"
    )


def count_user_jobs(
    user_id: str,
) -> int:

    with SessionLocal() as db:

        statement = (
            select(func.count())
            .select_from(ResearchJob)
            .where(
                ResearchJob.user_id == user_id
            )
        )

        return db.execute(
            statement
        ).scalar_one()


def test_deactivated_account_loses_access(
    environment: AuthenticationTestEnvironment,
) -> None:

    user_id, username = environment.create_user()

    client = environment.create_client()

    login(
        client,
        username,
    )

    response = request_as_user(
        client,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        200,
    )

    with SessionLocal() as db:

        user = db.get(
            UserAccount,
            user_id,
        )

        assert user is not None

        user.is_active = False

        db.commit()

    response = request_as_user(
        client,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        401,
    )

    response = request_as_user(
        client,
        "GET",
        "/api/auth/me",
    )

    assert_status(
        response,
        401,
    )

    print(
        "Deactivated account access correctly rejected."
    )


def test_revoked_session_cannot_be_reused(
    environment: AuthenticationTestEnvironment,
) -> None:

    user_id, username = environment.create_user()

    client = environment.create_client()

    session_token, csrf_token = login(
        client,
        username,
    )

    response = request_as_user(
        client,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        200,
    )

    response = request_as_user(
        client,
        "POST",
        "/api/auth/logout",
        csrf_token=csrf_token,
    )

    assert_status(
        response,
        204,
    )

    with SessionLocal() as db:

        session = db.scalar(
            select(UserSession).where(
                UserSession.token_hash
                == hash_token(session_token)
            )
        )

        assert session is not None

        assert session.user_id == user_id

        assert session.revoked_at is not None

    client.cookies.set(
        SESSION_COOKIE_NAME,
        session_token,
        path="/api",
    )

    response = request_as_user(
        client,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        401,
    )

    print(
        "Revoked session reuse correctly rejected."
    )


def test_password_change_requirement_blocks_research(
    environment: AuthenticationTestEnvironment,
) -> None:

    user_id, username = environment.create_user()

    client = environment.create_client()

    login(
        client,
        username,
    )

    response = request_as_user(
        client,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        200,
    )

    with SessionLocal() as db:

        user = db.get(
            UserAccount,
            user_id,
        )

        assert user is not None

        user.must_change_password = True

        db.commit()

    response = request_as_user(
        client,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        403,
    )

    response = request_as_user(
        client,
        "GET",
        "/api/auth/me",
    )

    assert_status(
        response,
        200,
    )

    assert (
        response.json()["user"][
            "must_change_password"
        ]
        is True
    )

    print(
        "Mandatory password change restriction passed."
    )


def test_csrf_protection_prevents_modification(
    environment: AuthenticationTestEnvironment,
) -> None:

    user_id, username = environment.create_user()

    client = environment.create_client()

    session_token, csrf_token = login(
        client,
        username,
    )

    initial_count = count_user_jobs(
        user_id
    )

    payload = {
        "topic": "Unauthorized CSRF research",
        "scope": "Security test",
    }

    response = request_as_user(
        client,
        "POST",
        "/api/research/jobs",
        json_body=payload,
    )

    assert_status(
        response,
        403,
    )

    response = request_as_user(
        client,
        "POST",
        "/api/research/jobs",
        csrf_token="invalid-csrf-token",
        json_body=payload,
    )

    assert_status(
        response,
        403,
    )

    response = request_as_user(
        client,
        "POST",
        "/api/research/jobs",
        csrf_token=csrf_token,
        json_body=payload,
        origin="https://untrusted.example",
    )

    assert_status(
        response,
        403,
    )

    response = request_as_user(
        client,
        "POST",
        "/api/research/jobs",
        csrf_token=csrf_token,
        json_body=payload,
        origin=None,
    )

    assert_status(
        response,
        403,
    )

    final_count = count_user_jobs(
        user_id
    )

    assert final_count == initial_count

    print(
        "CSRF and origin validation passed."
    )


def test_ordinary_user_cannot_access_admin_endpoints(
    environment: AuthenticationTestEnvironment,
) -> None:

    user_id, username = environment.create_user()

    target_id, target_username = (
        environment.create_user(
            approval_status="pending",
            is_active=True,
        )
    )

    client = environment.create_client()

    session_token, csrf_token = login(
        client,
        username,
    )

    response = request_as_user(
        client,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        200,
    )

    response = request_as_user(
        client,
        "GET",
        "/api/admin/users",
    )

    assert_status(
        response,
        403,
    )

    response = request_as_user(
        client,
        "POST",
        f"/api/admin/users/{target_id}/approve",
        csrf_token=csrf_token,
    )

    assert_status(
        response,
        403,
    )

    response = request_as_user(
        client,
        "POST",
        f"/api/admin/users/{target_id}/reject",
        csrf_token=csrf_token,
    )

    assert_status(
        response,
        403,
    )

    with SessionLocal() as db:

        target = db.get(
            UserAccount,
            target_id,
        )

        assert target is not None

        assert target.approval_status == "pending"

        assert target.approved_at is None

        assert target.is_active is True

    print(
        "Ordinary user administrator access rejected."
    )



def test_expired_session_is_rejected(
    environment: AuthenticationTestEnvironment,
) -> None:

    user_id, username = environment.create_user()

    client = environment.create_client()

    session_token, csrf_token = login(
        client,
        username,
    )

    response = request_as_user(
        client,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        200,
    )

    with SessionLocal() as db:

        session = db.scalar(
            select(UserSession).where(
                UserSession.token_hash
                == hash_token(session_token)
            )
        )

        assert session is not None

        session.expires_at = (
            utc_now() - timedelta(minutes=1)
        )

        db.commit()

    response = request_as_user(
        client,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        401,
    )

    print(
        "Expired session correctly rejected."
    )


def test_csrf_token_rotation(
    environment: AuthenticationTestEnvironment,
) -> None:

    user_id, username = environment.create_user()

    client = environment.create_client()

    session_token, original_csrf = login(
        client,
        username,
    )

    response = request_as_user(
        client,
        "GET",
        "/api/auth/me",
    )

    assert_status(
        response,
        200,
    )

    rotated_csrf = response.json()[
        "csrf_token"
    ]

    assert rotated_csrf != original_csrf

    response = request_as_user(
        client,
        "POST",
        "/api/auth/logout",
        csrf_token=original_csrf,
    )

    assert_status(
        response,
        403,
    )

    response = request_as_user(
        client,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        200,
    )

    response = request_as_user(
        client,
        "POST",
        "/api/auth/logout",
        csrf_token=rotated_csrf,
    )

    assert_status(
        response,
        204,
    )

    print(
        "CSRF token rotation correctly enforced."
    )


def test_password_change_revokes_all_sessions(
    environment: AuthenticationTestEnvironment,
) -> None:

    user_id, username = environment.create_user()

    client_a = environment.create_client()

    client_b = environment.create_client()

    session_a, csrf_a = login(
        client_a,
        username,
    )

    session_b, csrf_b = login(
        client_b,
        username,
    )

    assert session_a != session_b

    for client in [
        client_a,
        client_b,
    ]:

        response = request_as_user(
            client,
            "GET",
            "/api/research/jobs",
        )

        assert_status(
            response,
            200,
        )

    new_password = (
        "UpdatedAuthenticationPassword123!"
    )

    response = request_as_user(
        client_a,
        "POST",
        "/api/auth/change-password",
        csrf_token=csrf_a,
        json_body={
            "current_password": TEST_PASSWORD,
            "new_password": new_password,
        },
    )

    assert_status(
        response,
        200,
    )

    with SessionLocal() as db:

        user = db.get(
            UserAccount,
            user_id,
        )

        assert user is not None

        assert verify_password(
            new_password,
            user.password_hash,
        )

        sessions = db.scalars(
            select(UserSession).where(
                UserSession.user_id == user_id
            )
        ).all()

        assert len(sessions) == 2

        for session in sessions:

            assert session.revoked_at is not None

    client_a.cookies.set(
        SESSION_COOKIE_NAME,
        session_a,
        path="/api",
    )

    response = request_as_user(
        client_a,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        401,
    )

    response = request_as_user(
        client_b,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        401,
    )

    print(
        "Password change revoked all sessions."
    )


def test_pending_and_rejected_accounts_cannot_login(
    environment: AuthenticationTestEnvironment,
) -> None:

    for approval_status in [
        "pending",
        "rejected",
    ]:

        user_id, username = environment.create_user(
            approval_status=approval_status,
            is_active=True,
        )

        client = environment.create_client()

        response = client.post(
            "/api/auth/login",
            json={
                "username": username,
                "password": TEST_PASSWORD,
            },
            headers={
                "Origin": BASE_URL,
            },
        )

        assert_status(
            response,
            401,
        )

        assert client.cookies.get(
            SESSION_COOKIE_NAME
        ) is None

        with SessionLocal() as db:

            sessions = db.scalars(
                select(UserSession).where(
                    UserSession.user_id == user_id
                )
            ).all()

            assert len(sessions) == 0

        print(
            f"{approval_status.capitalize()} "
            "account login correctly rejected."
        )


def test_logout_only_revokes_current_session(
    environment: AuthenticationTestEnvironment,
) -> None:

    user_id, username = environment.create_user()

    client_a = environment.create_client()

    client_b = environment.create_client()

    session_a, csrf_a = login(
        client_a,
        username,
    )

    session_b, csrf_b = login(
        client_b,
        username,
    )

    assert session_a != session_b

    response = request_as_user(
        client_a,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        200,
    )

    response = request_as_user(
        client_b,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        200,
    )

    response = request_as_user(
        client_a,
        "POST",
        "/api/auth/logout",
        csrf_token=csrf_a,
    )

    assert_status(
        response,
        204,
    )

    with SessionLocal() as db:

        stored_a = db.scalar(
            select(UserSession).where(
                UserSession.token_hash
                == hash_token(session_a)
            )
        )

        stored_b = db.scalar(
            select(UserSession).where(
                UserSession.token_hash
                == hash_token(session_b)
            )
        )

        assert stored_a is not None

        assert stored_b is not None

        assert stored_a.revoked_at is not None

        assert stored_b.revoked_at is None

    client_a.cookies.set(
        SESSION_COOKIE_NAME,
        session_a,
        path="/api",
    )

    response = request_as_user(
        client_a,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        401,
    )

    response = request_as_user(
        client_b,
        "GET",
        "/api/research/jobs",
    )

    assert_status(
        response,
        200,
    )

    print(
        "Logout correctly preserved "
        "the independent session."
    )

