
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient

from sqlalchemy import text

from api.dependencies import (
    get_current_user_id,
    get_db,
)

from api.main import app

from persistence.research_job_repository import (
    ResearchJobRepository,
)

from test_research_workflow_user_questions_sql import (
    test_environment,
)


@pytest.fixture
def api_environment(
    test_environment,
):

    Session, user_id = test_environment

    # This is an additional safeguard. The imported
    # test_environment fixture must itself select the
    # test database before creating any records.

    with Session() as db:

        database_name = db.execute(
            text("SELECT DB_NAME()")
        ).scalar_one()

        assert database_name == "LGResearcher_Test", (
            "API integration tests must use "
            "LGResearcher_Test, not "
            f"{database_name!r}."
        )

    def override_get_db():

        with Session() as db:

            yield db

    def override_get_current_user_id():

        return user_id

    app.dependency_overrides[get_db] = (
        override_get_db
    )

    app.dependency_overrides[get_current_user_id] = (
        override_get_current_user_id
    )

    try:

        with TestClient(app) as client:

            yield client, Session, user_id

    finally:

        app.dependency_overrides.clear()


def create_draft(
    client,
    topic="Quantum computing and Bitcoin",
    scope="Cryptographic threats and mitigations",
):

    response = client.post(
        "/api/research/jobs",
        json={
            "topic": topic,
            "scope": scope,
        },
    )

    assert response.status_code == 201, (
        response.text
    )

    return response.json()


def add_question(
    client,
    job_id,
    question,
):

    response = client.post(
        f"/api/research/jobs/{job_id}/questions",
        json={
            "question": question,
        },
    )

    assert response.status_code == 201, (
        response.text
    )

    return response.json()


def test_create_draft_job(
    api_environment,
):

    client, Session, user_id = api_environment

    job = create_draft(
        client=client,
    )

    assert job["id"] is not None
    assert job["topic"] == (
        "Quantum computing and Bitcoin"
    )

    assert job["scope"] == (
        "Cryptographic threats and mitigations"
    )

    assert job["status"] == "draft"
    assert job["research_session_id"] is None

    assert job["created_at"] is not None
    assert job["submitted_at"] is None
    assert job["completed_at"] is None

    assert job["questions"] == []

    with Session() as db:

        row = db.execute(
            text("""
                SELECT
                    user_id,
                    topic,
                    scope,
                    status
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job["id"],
            },
        ).one()

    assert row[0] == user_id
    assert row[1] == job["topic"]
    assert row[2] == job["scope"]
    assert row[3] == "draft"


def test_add_multiple_questions(
    api_environment,
):

    client, Session, user_id = api_environment

    job = create_draft(
        client=client,
    )

    questions = [
        "How does Shor's algorithm threaten Bitcoin?",
        "What post-quantum signatures could Bitcoin adopt?",
    ]

    created_question_ids = []

    for question in questions:

        result = add_question(
            client=client,
            job_id=job["id"],
            question=question,
        )

        assert result["research_job_id"] == (
            job["id"]
        )

        assert result["question"] == question

        created_question_ids.append(
            result["id"]
        )

    assert len(
        set(created_question_ids)
    ) == 2

    with Session() as db:

        rows = db.execute(
            text("""
                SELECT
                    id,
                    question
                FROM dbo.research_job_questions
                WHERE research_job_id = :job_id
                ORDER BY id
            """),
            {
                "job_id": job["id"],
            },
        ).all()

    assert len(rows) == 2

    assert [
        row[1]
        for row in rows
    ] == questions


def test_submit_draft_job(
    api_environment,
):

    client, Session, user_id = api_environment

    job = create_draft(
        client=client,
    )

    add_question(
        client=client,
        job_id=job["id"],
        question=(
            "What are the cryptographic risks?"
        ),
    )

    response = client.post(
        f"/api/research/jobs/{job['id']}/submit"
    )

    assert response.status_code == 200

    result = response.json()

    assert result["id"] == job["id"]
    assert result["status"] == "queued"

    with Session() as db:

        row = db.execute(
            text("""
                SELECT
                    status,
                    submitted_at,
                    research_session_id
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job["id"],
            },
        ).one()

    assert row[0] == "queued"
    assert row[1] is not None
    assert row[2] is None


def test_retrieve_job_with_questions(
    api_environment,
):

    client, Session, user_id = api_environment

    job = create_draft(
        client=client,
    )

    questions = [
        "What is Shor's algorithm?",
        "How could Bitcoin migrate to new signatures?",
    ]

    for question in questions:

        add_question(
            client=client,
            job_id=job["id"],
            question=question,
        )

    response = client.get(
        f"/api/research/jobs/{job['id']}"
    )

    assert response.status_code == 200

    result = response.json()

    assert result["id"] == job["id"]
    assert result["status"] == "draft"

    returned_questions = [
        question["question"]
        for question in result["questions"]
    ]

    assert returned_questions == questions

    for question in result["questions"]:

        assert isinstance(
            question["id"],
            int,
        )

        assert question["created_at"] is not None


@pytest.mark.parametrize(
    "topic",
    [
        "",
        "   ",
        "x" * 1001,
    ],
)
def test_reject_invalid_topic(
    api_environment,
    topic,
):

    client, Session, user_id = api_environment

    response = client.post(
        "/api/research/jobs",
        json={
            "topic": topic,
            "scope": None,
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "question",
    [
        "",
        "   ",
        "x" * 2001,
    ],
)
def test_reject_invalid_question(
    api_environment,
    question,
):

    client, Session, user_id = api_environment

    job = create_draft(
        client=client,
    )

    response = client.post(
        f"/api/research/jobs/{job['id']}/questions",
        json={
            "question": question,
        },
    )

    assert response.status_code == 422

    with Session() as db:

        count = db.execute(
            text("""
                SELECT COUNT(*)
                FROM dbo.research_job_questions
                WHERE research_job_id = :job_id
            """),
            {
                "job_id": job["id"],
            },
        ).scalar_one()

    assert count == 0


def test_cannot_add_question_after_submission(
    api_environment,
):

    client, Session, user_id = api_environment

    job = create_draft(
        client=client,
    )

    response = client.post(
        f"/api/research/jobs/{job['id']}/submit"
    )

    assert response.status_code == 200

    response = client.post(
        f"/api/research/jobs/{job['id']}/questions",
        json={
            "question": (
                "This question should be rejected."
            ),
        },
    )

    assert response.status_code == 409

    with Session() as db:

        count = db.execute(
            text("""
                SELECT COUNT(*)
                FROM dbo.research_job_questions
                WHERE research_job_id = :job_id
            """),
            {
                "job_id": job["id"],
            },
        ).scalar_one()

    assert count == 0


def test_cannot_submit_job_twice(
    api_environment,
):

    client, Session, user_id = api_environment

    job = create_draft(
        client=client,
    )

    first_response = client.post(
        f"/api/research/jobs/{job['id']}/submit"
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/api/research/jobs/{job['id']}/submit"
    )

    assert second_response.status_code == 409

    with Session() as db:

        row = db.execute(
            text("""
                SELECT
                    status,
                    submitted_at
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job["id"],
            },
        ).one()

    assert row[0] == "queued"
    assert row[1] is not None


def test_nonexistent_job_returns_404(
    api_environment,
):

    client, Session, user_id = api_environment

    missing_job_id = str(
        uuid4()
    )

    response = client.get(
        f"/api/research/jobs/{missing_job_id}"
    )

    assert response.status_code == 404


def test_user_cannot_access_another_users_job(
    api_environment,
):

    client, Session, user_id = api_environment

    job = create_draft(
        client=client,
    )

    other_user_id = str(
        uuid4()
    )

    def override_other_user():

        return other_user_id

    app.dependency_overrides[
        get_current_user_id
    ] = override_other_user

    response = client.get(
        f"/api/research/jobs/{job['id']}"
    )

    assert response.status_code == 404

    response = client.post(
        f"/api/research/jobs/{job['id']}/questions",
        json={
            "question": (
                "An unauthorized question."
            ),
        },
    )

    assert response.status_code == 404

    response = client.post(
        f"/api/research/jobs/{job['id']}/submit"
    )

    assert response.status_code == 404

    with Session() as db:

        repository = ResearchJobRepository(
            db
        )

        questions = repository.list_draft_questions(
            job_id=job["id"],
            user_id=user_id,
        )

        row = db.execute(
            text("""
                SELECT status
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job["id"],
            },
        ).one()

    assert questions == []
    assert row[0] == "draft"


def test_unknown_fields_are_rejected(
    api_environment,
):

    client, Session, user_id = api_environment

    response = client.post(
        "/api/research/jobs",
        json={
            "topic": "Test research topic",
            "scope": None,
            "user_id": str(uuid4()),
        },
    )

    assert response.status_code == 422


def test_api_uses_test_database(
    api_environment,
):

    client, Session, user_id = api_environment

    with Session() as db:

        database_name = db.execute(
            text("SELECT DB_NAME()")
        ).scalar_one()

    assert database_name == "LGResearcher_Test"

    job = create_draft(
        client=client,
    )

    with Session() as db:

        row = db.execute(
            text("""
                SELECT id
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job["id"],
            },
        ).one()

    assert row[0] == job["id"]


def test_multiple_jobs_without_research_sessions(
    api_environment,
):

    client, Session, user_id = api_environment

    first_job = create_draft(
        client=client,
        topic="Quantum computing and Bitcoin",
    )

    second_job = create_draft(
        client=client,
        topic="The aerodynamics of aircraft",
    )

    assert first_job["id"] != second_job["id"]

    with Session() as db:

        rows = db.execute(
            text("""
                SELECT
                    id,
                    research_session_id
                FROM dbo.research_jobs
                WHERE id IN (
                    :first_job_id,
                    :second_job_id
                )
            """),
            {
                "first_job_id": first_job["id"],
                "second_job_id": second_job["id"],
            },
        ).all()

    assert len(rows) == 2

    for row in rows:

        assert row[1] is None


def test_list_research_jobs_with_pagination(
    api_environment,
):

    client, Session, user_id = api_environment

    for index in range(3):

        create_draft(
            client=client,
            topic=f"Pagination research topic {index}",
        )

    response = client.get(
        "/api/research/jobs",
        params={
            "limit": 2,
            "offset": 0,
        },
    )

    assert response.status_code == 200

    first_page = response.json()

    assert first_page["limit"] == 2
    assert first_page["offset"] == 0
    assert first_page["total"] >= 3
    assert len(first_page["items"]) == 2

    response = client.get(
        "/api/research/jobs",
        params={
            "limit": 2,
            "offset": 2,
        },
    )

    assert response.status_code == 200

    second_page = response.json()

    first_page_ids = {
        job["id"]
        for job in first_page["items"]
    }

    second_page_ids = {
        job["id"]
        for job in second_page["items"]
    }

    assert first_page_ids.isdisjoint(
        second_page_ids
    )



def test_update_draft_job(
    api_environment,
):

    client, Session, user_id = api_environment

    job = create_draft(
        client=client,
    )

    response = client.patch(
        f"/api/research/jobs/{job['id']}",
        json={
            "topic": "Updated research topic",
            "scope": "Updated research scope",
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["topic"] == "Updated research topic"
    assert result["scope"] == "Updated research scope"
    assert result["status"] == "draft"

    with Session() as db:

        row = db.execute(
            text("""
                SELECT
                    topic,
                    scope
                FROM dbo.research_jobs
                WHERE id = :job_id
            """),
            {
                "job_id": job["id"],
            },
        ).one()

    assert row[0] == "Updated research topic"
    assert row[1] == "Updated research scope"



def test_cannot_update_submitted_job(
    api_environment,
):

    client, Session, user_id = api_environment

    job = create_draft(
        client=client,
    )

    response = client.post(
        f"/api/research/jobs/{job['id']}/submit"
    )

    assert response.status_code == 200

    response = client.patch(
        f"/api/research/jobs/{job['id']}",
        json={
            "topic": "Unauthorized update",
            "scope": None,
        },
    )

    assert response.status_code == 409



def test_remove_draft_question(
    api_environment,
):

    client, Session, user_id = api_environment

    job = create_draft(
        client=client,
    )

    first_question = add_question(
        client=client,
        job_id=job["id"],
        question="First research question",
    )

    second_question = add_question(
        client=client,
        job_id=job["id"],
        question="Second research question",
    )

    response = client.delete(
        (
            f"/api/research/jobs/{job['id']}"
            f"/questions/{first_question['id']}"
        )
    )

    assert response.status_code == 204

    response = client.get(
        f"/api/research/jobs/{job['id']}"
    )

    assert response.status_code == 200

    questions = response.json()["questions"]

    assert len(questions) == 1

    assert questions[0]["id"] == (
        second_question["id"]
    )



def test_cannot_remove_submitted_question(
    api_environment,
):

    client, Session, user_id = api_environment

    job = create_draft(
        client=client,
    )

    question = add_question(
        client=client,
        job_id=job["id"],
        question="Research question",
    )

    response = client.post(
        f"/api/research/jobs/{job['id']}/submit"
    )

    assert response.status_code == 200

    response = client.delete(
        (
            f"/api/research/jobs/{job['id']}"
            f"/questions/{question['id']}"
        )
    )

    assert response.status_code == 409

    response = client.get(
        f"/api/research/jobs/{job['id']}"
    )

    questions = response.json()["questions"]

    assert len(questions) == 1