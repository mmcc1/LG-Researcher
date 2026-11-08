
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient

from sqlalchemy import func, select, text

from persistence.database import engine, SessionLocal
from persistence.models import ResearchJob, UserAccount, UserSession

from api.main import app

from security.password_hasher import hash_password


BASE_URL = "https://127.0.0.1:8000"

TEST_PASSWORD = "AdminQueueTestPassword123!"


def utc_now() -> datetime:

    return datetime.now(
        timezone.utc
    ).replace(tzinfo=None)


class AdminQueueTestEnvironment:

    def __init__(self):

        self.user_ids: list[str] = []

        self.job_ids: list[str] = []

        self.clients: list[TestClient] = []

    def create_user(
        self,
        role: str = "user",
    ) -> tuple[str, str]:

        user_id = str(uuid4())

        username = (
            f"admin_queue_test_{uuid4().hex[:12]}"
        )

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
            created_at=utc_now(),
            approved_at=utc_now(),
            email_reports_enabled=False,
        )

        with SessionLocal() as db:

            db.add(user)

            db.commit()

        self.user_ids.append(user_id)

        return user_id, username

    def create_job(
        self,
        user_id: str,
        status: str,
        topic: str,
        created_at: datetime | None = None,
    ) -> str:

        job_id = str(uuid4())

        if created_at is None:

            created_at = utc_now()

        job = ResearchJob(
            id=job_id,
            user_id=user_id,
            research_session_id=None,
            topic=topic,
            scope=None,
            status=status,
            created_at=created_at,
            submitted_at=None,
            started_at=None,
            completed_at=None,
            last_error=None,
            execution_owner=None,
            lease_expires_at=None,
            lease_version=0,
        )

        with SessionLocal() as db:

            db.add(job)

            db.commit()

        self.job_ids.append(job_id)

        return job_id

    def create_client(self) -> TestClient:

        client = TestClient(
            app,
            base_url=BASE_URL,
        )

        self.clients.append(client)

        return client

    def cleanup(self) -> None:

        for client in self.clients:

            client.close()

        with SessionLocal() as db:

            if self.job_ids:

                db.query(ResearchJob).filter(
                    ResearchJob.id.in_(
                        self.job_ids
                    )
                ).delete(
                    synchronize_session=False
                )

            if self.user_ids:

                db.query(UserSession).filter(
                    UserSession.user_id.in_(
                        self.user_ids
                    )
                ).delete(
                    synchronize_session=False
                )

                db.query(UserAccount).filter(
                    UserAccount.id.in_(
                        self.user_ids
                    )
                ).delete(
                    synchronize_session=False
                )

            db.commit()


@pytest.fixture
def environment() -> Generator[
    AdminQueueTestEnvironment,
    None,
    None,
]:

    with engine.connect() as connection:

        database_name = connection.execute(
            text("SELECT DB_NAME()")
        ).scalar_one()

    if database_name != "Researcher":

        pytest.fail(
            "Refusing to run tests against "
            f"database '{database_name}'."
        )

    test_environment = (
        AdminQueueTestEnvironment()
    )

    try:

        yield test_environment

    finally:

        test_environment.cleanup()


def login(
    client: TestClient,
    username: str,
) -> None:

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


def assert_status(
    response,
    expected_status: int,
) -> None:

    assert response.status_code == expected_status, (
        f"Expected HTTP {expected_status}, "
        f"received HTTP {response.status_code}: "
        f"{response.text}"
    )


def test_administrator_can_view_jobs_across_users(
    environment: AdminQueueTestEnvironment,
) -> None:

    admin_id, admin_username = (
        environment.create_user(
            role="admin"
        )
    )

    user_a_id, user_a_username = (
        environment.create_user()
    )

    user_b_id, user_b_username = (
        environment.create_user()
    )

    job_a_id = environment.create_job(
        user_id=user_a_id,
        status="draft",
        topic="Admin queue test topic A",
    )

    job_b_id = environment.create_job(
        user_id=user_b_id,
        status="queued",
        topic="Admin queue test topic B",
    )

    client = environment.create_client()

    login(
        client,
        admin_username,
    )

    response = client.get(
        "/api/admin/research/jobs",
        params={
            "limit": 100,
            "offset": 0,
        },
    )

    assert_status(
        response,
        200,
    )

    payload = response.json()

    assert "items" in payload

    assert "total" in payload

    assert payload["limit"] == 100

    assert payload["offset"] == 0

    returned_ids = {
        item["id"]
        for item in payload["items"]
    }

    # The database may contain other jobs.
    # Check our own records without assuming
    # the entire database is empty.

    if (
        job_a_id not in returned_ids
        or job_b_id not in returned_ids
    ):

        # Query by their unique test topics
        # through additional pages if needed.
        offset = 100

        while offset < payload["total"]:

            next_response = client.get(
                "/api/admin/research/jobs",
                params={
                    "limit": 100,
                    "offset": offset,
                },
            )

            assert_status(
                next_response,
                200,
            )

            next_payload = next_response.json()

            returned_ids.update(
                item["id"]
                for item in next_payload["items"]
            )

            offset += 100

    assert job_a_id in returned_ids

    assert job_b_id in returned_ids

    print(
        "Administrator can view jobs "
        "belonging to multiple users."
    )


def test_ordinary_user_cannot_access_queue(
    environment: AdminQueueTestEnvironment,
) -> None:

    user_id, username = (
        environment.create_user()
    )

    client = environment.create_client()

    login(
        client,
        username,
    )

    for endpoint in [
        "/api/admin/research/jobs",
        "/api/admin/research/jobs/summary",
    ]:

        response = client.get(
            endpoint
        )

        assert_status(
            response,
            403,
        )

    print(
        "Ordinary user correctly denied "
        "administrative queue access."
    )


def test_status_filtering(
    environment: AdminQueueTestEnvironment,
) -> None:

    admin_id, admin_username = (
        environment.create_user(
            role="admin"
        )
    )

    user_id, username = (
        environment.create_user()
    )

    draft_id = environment.create_job(
        user_id=user_id,
        status="draft",
        topic="Queue filtering draft",
    )

    queued_id = environment.create_job(
        user_id=user_id,
        status="queued",
        topic="Queue filtering queued",
    )

    client = environment.create_client()

    login(
        client,
        admin_username,
    )

    response = client.get(
        "/api/admin/research/jobs",
        params={
            "job_status": "draft",
            "limit": 100,
        },
    )

    assert_status(
        response,
        200,
    )

    payload = response.json()

    assert all(
        item["status"] == "draft"
        for item in payload["items"]
    )

    # The queued job must never appear
    # in the draft-filtered result.

    returned_ids = {
        item["id"]
        for item in payload["items"]
    }

    assert queued_id not in returned_ids

    # Verify the draft record directly
    # using an unfiltered database query.

    with SessionLocal() as db:

        draft_job = db.get(
            ResearchJob,
            draft_id,
        )

        assert draft_job is not None

        assert draft_job.status == "draft"

    print(
        "Research queue status filtering passed."
    )


def test_queue_pagination(
    environment: AdminQueueTestEnvironment,
) -> None:

    admin_id, admin_username = (
        environment.create_user(
            role="admin"
        )
    )

    user_id, username = (
        environment.create_user()
    )

    now = utc_now()

    created_ids = []

    for index in range(5):

        job_id = environment.create_job(
            user_id=user_id,
            status="pagination_test",
            topic=f"Pagination test {index}",
            created_at=(
                now + timedelta(seconds=index)
            ),
        )

        created_ids.append(job_id)

    client = environment.create_client()

    login(
        client,
        admin_username,
    )

    first_response = client.get(
        "/api/admin/research/jobs",
        params={
            "job_status": "pagination_test",
            "limit": 2,
            "offset": 0,
        },
    )

    second_response = client.get(
        "/api/admin/research/jobs",
        params={
            "job_status": "pagination_test",
            "limit": 2,
            "offset": 2,
        },
    )

    third_response = client.get(
        "/api/admin/research/jobs",
        params={
            "job_status": "pagination_test",
            "limit": 2,
            "offset": 4,
        },
    )

    for response in [
        first_response,
        second_response,
        third_response,
    ]:

        assert_status(
            response,
            200,
        )

    first = first_response.json()

    second = second_response.json()

    third = third_response.json()

    # This status is unique to this test.
    # It should have exactly five records.

    assert first["total"] == 5

    assert second["total"] == 5

    assert third["total"] == 5

    assert len(first["items"]) == 2

    assert len(second["items"]) == 2

    assert len(third["items"]) == 1

    returned_ids = [
        item["id"]
        for payload in [
            first,
            second,
            third,
        ]
        for item in payload["items"]
    ]

    assert len(set(returned_ids)) == 5

    assert set(returned_ids) == set(
        created_ids
    )

    print(
        "Research queue pagination passed."
    )


def test_summary_matches_database(
    environment: AdminQueueTestEnvironment,
) -> None:

    admin_id, admin_username = (
        environment.create_user(
            role="admin"
        )
    )

    user_id, username = (
        environment.create_user()
    )

    environment.create_job(
        user_id=user_id,
        status="draft",
        topic="Summary draft",
    )

    environment.create_job(
        user_id=user_id,
        status="queued",
        topic="Summary queued",
    )

    environment.create_job(
        user_id=user_id,
        status="completed",
        topic="Summary completed",
    )

    client = environment.create_client()

    login(
        client,
        admin_username,
    )

    response = client.get(
        "/api/admin/research/jobs/summary"
    )

    assert_status(
        response,
        200,
    )

    payload = response.json()

    returned_counts = {
        item["status"]: item["count"]
        for item in payload["statuses"]
    }

    with SessionLocal() as db:

        rows = db.execute(
            select(
                ResearchJob.status,
                func.count(),
            ).group_by(
                ResearchJob.status
            )
        ).all()

    database_counts = {
        status: count
        for status, count in rows
    }

    assert returned_counts == database_counts

    assert payload["total"] == sum(
        database_counts.values()
    )

    print(
        "Administrative summary matches "
        "SQL Server job counts."
    )


def test_unauthenticated_queue_access_is_rejected(
    environment: AdminQueueTestEnvironment,
) -> None:

    client = environment.create_client()

    for endpoint in [
        "/api/admin/research/jobs",
        "/api/admin/research/jobs/summary",
    ]:

        response = client.get(
            endpoint
        )

        assert_status(
            response,
            401,
        )

    print(
        "Unauthenticated queue access "
        "correctly rejected."
    )
