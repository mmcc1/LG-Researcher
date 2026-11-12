
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from application.research_job_heartbeat import (
    ResearchJobLeaseLost,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
)

from nodes.select_question import (
    SelectQuestionNode,
)


@pytest.fixture
def execution_lease():

    return ExecutionLease(
        session_id="test-session-id",
        owner="test-worker",
        version=1,
        expires_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def session_factory():

    return MagicMock()


def create_config(
    execution_lease,
    execution_guard=None,
):

    return {
        "configurable": {
            "execution_lease": execution_lease,
            "execution_guard": execution_guard,
        },
    }


def test_guard_checked_before_question_selection(
    execution_lease,
    session_factory,
):

    node = SelectQuestionNode(
        session_factory=session_factory,
    )

    guard = MagicMock(
        side_effect=ResearchJobLeaseLost(
            "Job lease lost."
        )
    )

    config = create_config(
        execution_lease,
        execution_guard=guard,
    )

    with pytest.raises(
        ResearchJobLeaseLost,
        match="Job lease lost",
    ):

        node(
            {"session_id": "test-session-id"},
            config,
        )

    guard.assert_called_once()

    session_factory.assert_not_called()


def test_guard_checked_after_question_selection(
    execution_lease,
    session_factory,
):

    node = SelectQuestionNode(
        session_factory=session_factory,
    )

    guard = MagicMock(
        side_effect=[
            None,
            ResearchJobLeaseLost(
                "Job lease lost after selection."
            ),
        ],
    )

    config = create_config(
        execution_lease,
        execution_guard=guard,
    )

    question = SimpleNamespace(
        id=42,
        question="Test research question?",
    )

    with patch(
        "nodes.select_question."
        "ResearchSessionRepository"
    ) as repository_class:

        repository = repository_class.return_value

        repository.select_question_fenced.return_value = (
            question
        )

        with pytest.raises(
            ResearchJobLeaseLost,
            match="lost after selection",
        ):

            node(
                {"session_id": "test-session-id"},
                config,
            )

        repository.select_question_fenced.assert_called_once_with(
            session_id="test-session-id",
            lease=execution_lease,
        )

    assert guard.call_count == 2


def test_node_without_guard_remains_compatible(
    execution_lease,
    session_factory,
):

    node = SelectQuestionNode(
        session_factory=session_factory,
    )

    config = create_config(
        execution_lease,
    )

    with patch(
        "nodes.select_question."
        "ResearchSessionRepository"
    ) as repository_class:

        repository = repository_class.return_value

        repository.select_question_fenced.return_value = None

        result = node(
            {"session_id": "test-session-id"},
            config,
        )

    assert result == {
        "current_question_id": None,
        "current_question": None,
        "current_search_attempt_id": None,
    }


def test_invalid_guard_is_rejected(
    execution_lease,
    session_factory,
):

    node = SelectQuestionNode(
        session_factory=session_factory,
    )

    config = create_config(
        execution_lease,
        execution_guard="not-callable",
    )

    with pytest.raises(
        TypeError,
        match="must be callable",
    ):

        node(
            {"session_id": "test-session-id"},
            config,
        )

    session_factory.assert_not_called()
