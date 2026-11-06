
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


def run_with_graph_callback(
    execution_lease,
    session_factory,
    graph_callback,
    job_guard=None,
    heartbeat=None,
):

    graph = MagicMock()

    graph.invoke.side_effect = graph_callback

    service = ResearchWorkflowService(
        graph=graph,
        session_factory=session_factory,
    )

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

        if heartbeat is not None:

            heartbeat_class.return_value = heartbeat

        active_heartbeat = heartbeat_class.return_value

        try:

            return service._execute_with_lease(
                session_id="test-session-id",
                topic="Test topic",
                scope=None,
                resume=False,
                execution_target="complete",
                execution_guard=job_guard,
            )

        finally:

            active_heartbeat.stop.assert_called_once()

            lease_repository.release.assert_called_once()


def test_execution_lease_lost_during_graph(
    execution_lease,
    session_factory,
):

    heartbeat = MagicMock()

    def graph_callback(state, config):

        combined_guard = config["configurable"][
            "execution_guard"
        ]

        heartbeat.check.side_effect = (
            ExecutionLeaseLost(
                "Execution lease lost during graph."
            )
        )

        combined_guard()

    with pytest.raises(
        ExecutionLeaseLost,
        match="lost during graph",
    ):

        run_with_graph_callback(
            execution_lease=execution_lease,
            session_factory=session_factory,
            graph_callback=graph_callback,
            heartbeat=heartbeat,
        )

    heartbeat.start.assert_called_once()

    heartbeat.stop.assert_called_once()


def test_job_lease_lost_during_graph(
    execution_lease,
    session_factory,
):

    job_guard = MagicMock()

    def graph_callback(state, config):

        combined_guard = config["configurable"][
            "execution_guard"
        ]

        job_guard.side_effect = (
            ResearchJobLeaseLost(
                "Job lease lost during graph."
            )
        )

        combined_guard()

    with pytest.raises(
        ResearchJobLeaseLost,
        match="lost during graph",
    ):

        run_with_graph_callback(
            execution_lease=execution_lease,
            session_factory=session_factory,
            graph_callback=graph_callback,
            job_guard=job_guard,
        )
