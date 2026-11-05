
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from persistence.research_session_repository import (
    RecoveryNotEligible,
)

from persistence.execution_lease_repository import (
    ExecutionLeaseRepository,
    ExecutionLeaseUnavailable,
)


@pytest.fixture
def workflow_service():

    graph = MagicMock()

    session_factory = MagicMock()

    return ResearchWorkflowService(
        graph=graph,
        session_factory=session_factory,
    )


def create_research_session(
    status: str,
):

    return SimpleNamespace(
        id="test-session-id",
        topic="Test research topic",
        scope="Test scope",
        status=status,
        pause_requested=False,
    )


def test_execute_existing_created_session(
    workflow_service,
):

    research_session = create_research_session(
        status="created",
    )

    with patch(
        "application.research_workflow_service."
        "ResearchSessionRepository"
    ) as repository_class:

        repository = repository_class.return_value

        repository.get.return_value = research_session

        with patch.object(
            workflow_service,
            "_execute_with_lease",
        ) as execute:

            workflow_service.execute_existing(
                "test-session-id"
            )

            execute.assert_called_once_with(
                session_id="test-session-id",
                topic="Test research topic",
                scope="Test scope",
                resume=False,
                execution_target="complete",
                execution_guard=None,
            )


def test_execute_existing_interrupted_session(
    workflow_service,
):

    research_session = create_research_session(
        status="researching",
    )

    with patch(
        "application.research_workflow_service."
        "ResearchSessionRepository"
    ) as repository_class:

        repository = repository_class.return_value

        repository.get.return_value = research_session

        with patch.object(
            workflow_service,
            "_execute_with_lease",
        ) as execute:

            workflow_service.execute_existing(
                "test-session-id"
            )

            execute.assert_called_once_with(
                session_id="test-session-id",
                topic="Test research topic",
                scope="Test scope",
                resume=True,
                execution_target="complete",
                recovery=True,
                execution_guard=None,
            )


def test_execute_existing_completed_session(
    workflow_service,
):

    research_session = create_research_session(
        status="completed",
    )

    with patch(
        "application.research_workflow_service."
        "ResearchSessionRepository"
    ) as repository_class:

        repository = repository_class.return_value

        repository.get.return_value = research_session

        with patch.object(
            workflow_service,
            "_execute_with_lease",
        ) as execute:

            with pytest.raises(
                RecoveryNotEligible
            ):

                workflow_service.execute_existing(
                    "test-session-id"
                )

            execute.assert_not_called()


def test_execute_existing_paused_session(
    workflow_service,
):

    research_session = create_research_session(
        status="paused",
    )

    with patch(
        "application.research_workflow_service."
        "ResearchSessionRepository"
    ) as repository_class:

        repository = repository_class.return_value

        repository.get.return_value = research_session

        with patch.object(
            workflow_service,
            "_execute_with_lease",
        ) as execute:

            with pytest.raises(
                RecoveryNotEligible
            ):

                workflow_service.execute_existing(
                    "test-session-id"
                )

            execute.assert_not_called()




def test_execute_existing_missing_session(
    workflow_service,
):

    with patch(
        "application.research_workflow_service."
        "ResearchSessionRepository"
    ) as repository_class:

        repository = repository_class.return_value

        repository.get.return_value = None

        with patch.object(
            workflow_service,
            "_execute_with_lease",
        ) as execute:

            with pytest.raises(
                ValueError,
                match="Research session not found",
            ):

                workflow_service.execute_existing(
                    "missing-session-id"
                )

            execute.assert_not_called()



def test_execute_existing_active_execution_lease(
    workflow_service,
):

    research_session = create_research_session(
        status="created",
    )

    with patch(
        "application.research_workflow_service."
        "ResearchSessionRepository"
    ) as repository_class:

        repository = repository_class.return_value

        repository.get.return_value = research_session

        with patch.object(
            ExecutionLeaseRepository,
            "acquire",
            side_effect=ExecutionLeaseUnavailable(
                "Session already has an active execution lease"
            ),
        ):

            with pytest.raises(
                ExecutionLeaseUnavailable
            ):

                workflow_service.execute_existing(
                    "test-session-id"
                )

    workflow_service.graph.invoke.assert_not_called()

