
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseFenceRejected,
)

from persistence.finding_repository import (
    FindingRepository,
)

from persistence.models import (
    Finding,
    SourceSummary,
)


def make_lease():

    return ExecutionLease(
        session_id="test-session",
        owner="test-worker",
        version=1,
        expires_at=(
            datetime.now(timezone.utc)
            + timedelta(minutes=2)
        ),
    )


def make_analysis():

    return SimpleNamespace(
        summary="Research summary",
        findings=[
            SimpleNamespace(
                claim="Finding one",
                evidence="Evidence one",
                relevance=0.9,
                confidence=0.8,
            ),
            SimpleNamespace(
                claim="Finding two",
                evidence="Evidence two",
                relevance=0.7,
                confidence=0.9,
            ),
        ],
    )


def make_database(
    ownership_valid=True,
    existing_analysis=None,
):

    db = Mock()

    ownership_row = (
        SimpleNamespace(id=100)
        if ownership_valid
        else None
    )

    db.execute.return_value.first.return_value = (
        ownership_row
    )

    db.query.return_value.filter.return_value.first.return_value = (
        existing_analysis
    )

    return db


@pytest.fixture
def fence_patch():

    with patch(
        "persistence.finding_repository."
        "ExecutionLeaseRepository"
    ) as repository_class:

        yield repository_class


def test_first_analysis_creates_summary_and_findings(
    fence_patch,
):

    db = make_database()

    repository = FindingRepository(db)

    lease = make_lease()

    analysis = make_analysis()

    repository.save_analysis(
        source_id=100,
        question_id=10,
        analysis=analysis,
        lease=lease,
    )

    fence_patch.return_value.fence.assert_called_once_with(
        lease
    )

    assert db.add.call_count == 3

    saved_objects = [
        call.args[0]
        for call in db.add.call_args_list
    ]

    summaries = [
        item
        for item in saved_objects
        if isinstance(item, SourceSummary)
    ]

    findings = [
        item
        for item in saved_objects
        if isinstance(item, Finding)
    ]

    assert len(summaries) == 1

    assert len(findings) == 2

    assert summaries[0].summary == "Research summary"

    assert summaries[0].source_id == 100

    assert summaries[0].research_question_id == 10

    assert findings[0].claim == "Finding one"

    assert findings[1].claim == "Finding two"

    db.commit.assert_called_once()

    db.rollback.assert_not_called()


def test_repeated_analysis_does_not_create_duplicates(
    fence_patch,
):

    existing_summary = SimpleNamespace(
        id=50,
        source_id=100,
        research_question_id=10,
    )

    db = make_database(
        existing_analysis=existing_summary,
    )

    repository = FindingRepository(db)

    lease = make_lease()

    repository.save_analysis(
        source_id=100,
        question_id=10,
        analysis=make_analysis(),
        lease=lease,
    )

    fence_patch.return_value.fence.assert_called_once_with(
        lease
    )

    db.add.assert_not_called()

    db.commit.assert_called_once()

    db.rollback.assert_not_called()


def test_invalid_execution_lease_prevents_writes(
    fence_patch,
):

    db = make_database()

    fence_patch.return_value.fence.side_effect = (
        ExecutionLeaseFenceRejected(
            "Execution lease rejected."
        )
    )

    repository = FindingRepository(db)

    with pytest.raises(
        ExecutionLeaseFenceRejected,
    ):

        repository.save_analysis(
            source_id=100,
            question_id=10,
            analysis=make_analysis(),
            lease=make_lease(),
        )

    db.execute.assert_not_called()

    db.add.assert_not_called()

    db.commit.assert_not_called()

    db.rollback.assert_called_once()


def test_invalid_source_ownership_is_rejected(
    fence_patch,
):

    db = make_database(
        ownership_valid=False,
    )

    repository = FindingRepository(db)

    with pytest.raises(
        ValueError,
        match="do not belong",
    ):

        repository.save_analysis(
            source_id=100,
            question_id=10,
            analysis=make_analysis(),
            lease=make_lease(),
        )

    db.add.assert_not_called()

    db.commit.assert_not_called()

    db.rollback.assert_called_once()


def test_database_failure_rolls_back(
    fence_patch,
):

    db = make_database()

    db.commit.side_effect = RuntimeError(
        "Database commit failed."
    )

    repository = FindingRepository(db)

    with pytest.raises(
        RuntimeError,
        match="Database commit failed",
    ):

        repository.save_analysis(
            source_id=100,
            question_id=10,
            analysis=make_analysis(),
            lease=make_lease(),
        )

    assert db.add.call_count == 3

    db.commit.assert_called_once()

    db.rollback.assert_called_once()
