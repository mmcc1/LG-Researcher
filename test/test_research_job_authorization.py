
from collections.abc import Generator
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient

from sqlalchemy import (
    select,
    text,
)

from sqlalchemy.orm import Session

from api.dependencies import get_db
from api.main import app

from persistence.database import (
    engine,
    SessionLocal,
)

from persistence.models import (
    ResearchJob,
    ResearchJobQuestion,
    UserAccount,
    UserSession,
)

from security.password_hasher import hash_password


BASE_URL = "https://127.0.0.1:8000"

TEST_PASSWORD = "AuthorizationTestPassword123!"

SESSION_COOKIE_NAME = "lg_researcher_session"


def utc_now() -> datetime:

    return datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )


@pytest.fixture
def test_environment() -> Generator[
    None,
    None,
    None,
]:

    with engine.connect() as connection:

        database_name = connection.execute(
            text("SELECT DB_NAME()")
        ).scalar_one()

    if database_name != "Researcher":

        pytest.fail(
            "Refusing to run authorization tests "
            f"against database '{database_name}'."
        )

    print(
        f"\nConnected to database: {database_name}"
    )

    yield


def create_client() -> TestClient:

    client = TestClient(
        app,
        base_url=BASE_URL,
    )

    return client


def create_test_user(
    role: str = "user",
) -> tuple[str, str]:

    user_id = str(
        uuid4()
    )

    username = (
        "authorization_"
        + user_id.replace("-", "")
    )

    now = utc_now()

    with SessionLocal() as db:

        user = UserAccount(
            id=user_id,
            username=username,
            email=None,
            password_hash=hash_password(
                TEST_PASSWORD
            ),
            is_active=True,
            role=role,
            approval_status="approved",
            must_change_password=False,
            approved_at=now,
            email_reports_enabled=False,
            created_at=now,
            last_login_at=None,
        )

        db.add(user)

        db.commit()

    return user_id, username


def login_user(
    client: TestClient,
    username: str,
) -> str:

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

    session_cookie = client.cookies.get(
        SESSION_COOKIE_NAME
    )

    assert session_cookie is not None

    csrf_token = response.json()[
        "csrf_token"
    ]

    return csrf_token


def request_as_user(
    client: TestClient,
    method: str,
    path: str,
    csrf_token: str,
    json_body: dict | None = None,
):

    headers = {
        "Origin": BASE_URL,
        "X-CSRF-Token": csrf_token,
    }

    request_options = {
        "headers": headers,
    }

    if json_body is not None:

        request_options["json"] = json_body

    return client.request(
        method,
        path,
        **request_options,
    )


def create_job(
    client: TestClient,
    csrf_token: str,
    topic: str,
) -> str:

    response = request_as_user(
        client=client,
        method="POST",
        path="/api/research/jobs",
        csrf_token=csrf_token,
        json_body={
            "topic": topic,
            "scope": "Authorization test.",
        },
    )

    assert response.status_code == 201, (
        response.text
    )

    return response.json()["id"]


def add_question(
    client: TestClient,
    csrf_token: str,
    job_id: str,
) -> int:

    response = request_as_user(
        client=client,
        method="POST",
        path=(
            f"/api/research/jobs/{job_id}/questions"
        ),
        csrf_token=csrf_token,
        json_body={
            "question": (
                "Does authorization prevent "
                "cross-user access?"
            ),
        },
    )

    assert response.status_code == 201, (
        response.text
    )

    return response.json()["id"]


def assert_status(
    response,
    expected_status: int,
) -> None:

    assert response.status_code == expected_status, (
        f"Expected {expected_status}, "
        f"received {response.status_code}: "
        f"{response.text}"
    )


def check_foreign_job_access(
    identity_name: str,
    client: TestClient,
    csrf_token: str,
    foreign_job_id: str,
    foreign_question_id: int,
) -> None:

    print(
        f"Checking {identity_name} "
        "against a foreign job..."
    )

    response = request_as_user(
        client=client,
        method="GET",
        path=(
            f"/api/research/jobs/{foreign_job_id}"
        ),
        csrf_token=csrf_token,
    )

    assert_status(
        response,
        404,
    )

    response = request_as_user(
        client=client,
        method="PATCH",
        path=(
            f"/api/research/jobs/{foreign_job_id}"
        ),
        csrf_token=csrf_token,
        json_body={
            "topic": "Unauthorized modification",
            "scope": None,
        },
    )

    assert_status(
        response,
        404,
    )

    response = request_as_user(
        client=client,
        method="POST",
        path=(
            f"/api/research/jobs/{foreign_job_id}"
            "/questions"
        ),
        csrf_token=csrf_token,
        json_body={
            "question": "Unauthorized question",
        },
    )

    assert_status(
        response,
        404,
    )

    response = request_as_user(
        client=client,
        method="DELETE",
        path=(
            f"/api/research/jobs/{foreign_job_id}"
            f"/questions/{foreign_question_id}"
        ),
        csrf_token=csrf_token,
    )

    assert_status(
        response,
        404,
    )

    response = request_as_user(
        client=client,
        method="POST",
        path=(
            f"/api/research/jobs/{foreign_job_id}"
            "/submit"
        ),
        csrf_token=csrf_token,
    )

    assert_status(
        response,
        404,
    )


def check_owned_job_access(
    identity_name: str,
    client: TestClient,
    csrf_token: str,
    expected_job_id: str,
) -> None:

    print(
        f"Checking {identity_name} "
        "can access their own job..."
    )

    response = request_as_user(
        client=client,
        method="GET",
        path="/api/research/jobs",
        csrf_token=csrf_token,
    )

    assert_status(
        response,
        200,
    )

    returned_ids = {
        item["id"]
        for item in response.json()["items"]
    }

    assert returned_ids == {
        expected_job_id
    }

    assert response.json()["total"] == 1

    response = request_as_user(
        client=client,
        method="GET",
        path=(
            f"/api/research/jobs/{expected_job_id}"
        ),
        csrf_token=csrf_token,
    )

    assert_status(
        response,
        200,
    )

    assert response.json()["id"] == (
        expected_job_id
    )


def verify_database_unchanged(
    job_a: str,
    job_b: str,
    user_a_id: str,
    user_b_id: str,
    question_a: int,
    question_b: int,
) -> None:

    with SessionLocal() as db:

        persisted_job_a = db.get(
            ResearchJob,
            job_a,
        )

        persisted_job_b = db.get(
            ResearchJob,
            job_b,
        )

        assert persisted_job_a is not None

        assert persisted_job_b is not None

        assert persisted_job_a.user_id == (
            user_a_id
        )

        assert persisted_job_b.user_id == (
            user_b_id
        )

        assert persisted_job_a.topic == (
            "Private research A"
        )

        assert persisted_job_b.topic == (
            "Private research B"
        )

        assert persisted_job_a.status == "draft"

        assert persisted_job_b.status == "draft"

        questions_a = db.scalars(
            select(ResearchJobQuestion).where(
                ResearchJobQuestion.research_job_id
                == job_a
            )
        ).all()

        questions_b = db.scalars(
            select(ResearchJobQuestion).where(
                ResearchJobQuestion.research_job_id
                == job_b
            )
        ).all()

        assert len(questions_a) == 1

        assert len(questions_b) == 1

        assert questions_a[0].id == (
            question_a
        )

        assert questions_b[0].id == (
            question_b
        )


def cleanup_test_records(
    created_user_ids: list[str],
    created_job_ids: list[str],
) -> None:

    print(
        "Cleaning up authorization test records..."
    )

    with SessionLocal() as db:

        if created_job_ids:

            questions = db.scalars(
                select(ResearchJobQuestion).where(
                    ResearchJobQuestion.research_job_id.in_(
                        created_job_ids
                    )
                )
            ).all()

            for question in questions:

                db.delete(question)

            db.flush()

            jobs = db.scalars(
                select(ResearchJob).where(
                    ResearchJob.id.in_(
                        created_job_ids
                    )
                )
            ).all()

            for job in jobs:

                db.delete(job)

            db.flush()

        if created_user_ids:

            sessions = db.scalars(
                select(UserSession).where(
                    UserSession.user_id.in_(
                        created_user_ids
                    )
                )
            ).all()

            for session in sessions:

                db.delete(session)

            db.flush()

            users = db.scalars(
                select(UserAccount).where(
                    UserAccount.id.in_(
                        created_user_ids
                    )
                )
            ).all()

            for user in users:

                db.delete(user)

        db.commit()

    print(
        "Authorization test cleanup completed."
    )


def test_research_job_user_isolation(
    test_environment,
) -> None:

    created_user_ids = []

    created_job_ids = []

    client_a = create_client()

    client_b = create_client()

    client_admin = create_client()

    try:

        user_a_id, username_a = create_test_user()

        created_user_ids.append(
            user_a_id
        )

        user_b_id, username_b = create_test_user()

        created_user_ids.append(
            user_b_id
        )

        admin_id, admin_username = create_test_user(
            role="admin"
        )

        created_user_ids.append(
            admin_id
        )

        csrf_a = login_user(
            client_a,
            username_a,
        )

        csrf_b = login_user(
            client_b,
            username_b,
        )

        csrf_admin = login_user(
            client_admin,
            admin_username,
        )

        job_a = create_job(
            client_a,
            csrf_a,
            "Private research A",
        )

        created_job_ids.append(
            job_a
        )

        job_b = create_job(
            client_b,
            csrf_b,
            "Private research B",
        )

        created_job_ids.append(
            job_b
        )

        question_a = add_question(
            client_a,
            csrf_a,
            job_a,
        )

        question_b = add_question(
            client_b,
            csrf_b,
            job_b,
        )

        check_foreign_job_access(
            identity_name="User A",
            client=client_a,
            csrf_token=csrf_a,
            foreign_job_id=job_b,
            foreign_question_id=question_b,
        )

        check_foreign_job_access(
            identity_name="User B",
            client=client_b,
            csrf_token=csrf_b,
            foreign_job_id=job_a,
            foreign_question_id=question_a,
        )

        check_foreign_job_access(
            identity_name="Administrator",
            client=client_admin,
            csrf_token=csrf_admin,
            foreign_job_id=job_a,
            foreign_question_id=question_a,
        )

        check_owned_job_access(
            identity_name="User A",
            client=client_a,
            csrf_token=csrf_a,
            expected_job_id=job_a,
        )

        check_owned_job_access(
            identity_name="User B",
            client=client_b,
            csrf_token=csrf_b,
            expected_job_id=job_b,
        )

        response = request_as_user(
            client=client_admin,
            method="GET",
            path="/api/research/jobs",
            csrf_token=csrf_admin,
        )

        assert_status(
            response,
            200,
        )

        assert response.json()["total"] == 0

        response = request_as_user(
            client=client_a,
            method="DELETE",
            path=(
                f"/api/research/jobs/{job_a}"
                f"/questions/{question_b}"
            ),
            csrf_token=csrf_a,
        )

        assert_status(
            response,
            409,
        )

        missing_job_id = str(
            uuid4()
        )

        response = request_as_user(
            client=client_a,
            method="GET",
            path=(
                f"/api/research/jobs/{missing_job_id}"
            ),
            csrf_token=csrf_a,
        )

        assert_status(
            response,
            404,
        )

        verify_database_unchanged(
            job_a=job_a,
            job_b=job_b,
            user_a_id=user_a_id,
            user_b_id=user_b_id,
            question_a=question_a,
            question_b=question_b,
        )

        print(
            "Cross-user authorization checks passed."
        )

    finally:

        client_a.close()

        client_b.close()

        client_admin.close()

        cleanup_test_records(
            created_user_ids=created_user_ids,
            created_job_ids=created_job_ids,
        )
