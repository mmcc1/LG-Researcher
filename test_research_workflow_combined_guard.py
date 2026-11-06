
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from application.execution_lease_heartbeat import (
    ExecutionLeaseLost,
)

from application.research_job_heartbeat import (
    ResearchJobLeaseLost,
)

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
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


def create_service(
    session_factory,
):

    graph = MagicMock()

    graph.invoke.return_value = {
        "session_id": "test-session-id",
        "status": "completed",
    }

    return ResearchWorkflowService(
        graph=graph,
        session_factory=session_factory,
    )


def execute_with_mocks(
    service,
    execution_lease,
    job_guard=None,
    heartbeat_failure=None,
):

    with (
        patch(
            "application.research_workflow_service."
            "ExecutionLeaseRepository"
        ) as lease_repository_class,
        patch(
            "application.research_workflow_service."
            "ResearchSessionRepository"
        ) as session_repository_class,
        patch(
            "application.research_workflow_service."
            "ExecutionLeaseHeartbeat"
        ) as heartbeat_class,
    ):

        lease_repository = (
            lease_repository_class.return_value
        )

        lease_repository.acquire.return_value = (
            execution_lease
        )

        lease_repository.release.return_value = True

        session_repository = (
            session_repository_class.return_value
        )

        session_repository.prepare_execution_fenced.return_value = (
            "Test topic",
            None,
        )

        heartbeat = heartbeat_class.return_value

        if heartbeat_failure is not None:

            heartbeat.check.side_effect = (
                heartbeat_failure
            )

        result = service._execute_with_lease(
            session_id="test-session-id",
            topic="Test topic",
            scope=None,
            resume=False,
            execution_target="complete",
            execution_guard=job_guard,
        )

        return result


def test_combined_guard_reaches_graph(
    execution_lease,
    session_factory,
):

    service = create_service(
        session_factory,
    )

    job_guard = MagicMock()

    execute_with_mocks(
        service=service,
        execution_lease=execution_lease,
        job_guard=job_guard,
    )

    assert service.graph.invoke.call_count == 1

    args, kwargs = service.graph.invoke.call_args

    config = kwargs["config"]

    combined_guard = config["configurable"][
        "execution_guard"
    ]

    assert callable(combined_guard)

    combined_guard()

    # Two preliminary checks, two checks surrounding
    # graph invocation, and the explicit test call.
    assert job_guard.call_count == 5


def test_execution_lease_loss_prevents_graph_invocation(
    execution_lease,
    session_factory,
):

    service = create_service(
        session_factory,
    )

    with pytest.raises(
        ExecutionLeaseLost,
        match="Execution lease lost",
    ):

        execute_with_mocks(
            service=service,
            execution_lease=execution_lease,
            heartbeat_failure=ExecutionLeaseLost(
                "Execution lease lost."
            ),
        )

    service.graph.invoke.assert_not_called()


def test_job_lease_loss_prevents_graph_invocation(
    execution_lease,
    session_factory,
):

    service = create_service(
        session_factory,
    )

    job_guard = MagicMock(
        side_effect=[
            None,
            None,
            ResearchJobLeaseLost(
                "Job lease lost."
            ),
        ],
    )

    with pytest.raises(
        ResearchJobLeaseLost,
        match="Job lease lost",
    ):

        execute_with_mocks(
            service=service,
            execution_lease=execution_lease,
            job_guard=job_guard,
        )

    service.graph.invoke.assert_not_called()


def test_cli_execution_without_job_guard(
    execution_lease,
    session_factory,
):

    service = create_service(
        session_factory,
    )

    execute_with_mocks(
        service=service,
        execution_lease=execution_lease,
    )

    assert service.graph.invoke.call_count == 1

    config = service.graph.invoke.call_args.kwargs[
        "config"
    ]

    combined_guard = config["configurable"][
        "execution_guard"
    ]

    assert callable(combined_guard)

    combined_guard()
