
from unittest.mock import MagicMock

import pytest

from application.execution_lease_heartbeat import (
    ExecutionLeaseLost,
)

from application.research_job_heartbeat import (
    ResearchJobLeaseLost,
)

from application.guarded_graph_node import (
    GuardedGraphNode,
)


def test_state_only_node_receives_state():

    received = []

    def node(state):

        received.append(state)

        return {
            "result": "success",
        }

    guard = MagicMock()

    wrapped = GuardedGraphNode(
        node=node,
    )

    result = wrapped(
        state={
            "session_id": "test-session",
        },
        config={
            "configurable": {
                "execution_guard": guard,
            },
        },
    )

    assert result == {
        "result": "success",
    }

    assert received == [
        {
            "session_id": "test-session",
        },
    ]

    assert guard.call_count == 2


def test_node_receives_config():

    received = []

    def node(state, config):

        received.append(
            config["configurable"][
                "execution_guard"
            ]
        )

        return {
            "result": "success",
        }

    guard = MagicMock()

    wrapped = GuardedGraphNode(
        node=node,
    )

    wrapped(
        state={},
        config={
            "configurable": {
                "execution_guard": guard,
            },
        },
    )

    assert received == [
        guard,
    ]

    assert guard.call_count == 2


def test_execution_lease_loss_prevents_node():

    node = MagicMock()

    guard = MagicMock(
        side_effect=ExecutionLeaseLost(
            "Execution lease lost."
        )
    )

    wrapped = GuardedGraphNode(
        node=node,
    )

    with pytest.raises(
        ExecutionLeaseLost,
    ):

        wrapped(
            state={},
            config={
                "configurable": {
                    "execution_guard": guard,
                },
            },
        )

    node.assert_not_called()


def test_job_lease_loss_after_node():

    node = MagicMock(
        return_value={
            "result": "success",
        }
    )

    guard = MagicMock(
        side_effect=[
            None,
            ResearchJobLeaseLost(
                "Job lease lost."
            ),
        ]
    )

    wrapped = GuardedGraphNode(
        node=node,
    )

    with pytest.raises(
        ResearchJobLeaseLost,
    ):

        wrapped(
            state={},
            config={
                "configurable": {
                    "execution_guard": guard,
                },
            },
        )

    node.assert_called_once()


def test_without_guard():

    node = MagicMock(
        return_value={
            "result": "success",
        }
    )

    wrapped = GuardedGraphNode(
        node=node,
    )

    result = wrapped(
        state={},
        config={
            "configurable": {},
        },
    )

    assert result == {
        "result": "success",
    }


def test_invalid_guard_rejected():

    node = MagicMock()

    wrapped = GuardedGraphNode(
        node=node,
    )

    with pytest.raises(
        TypeError,
        match="Execution guard must be callable",
    ):

        wrapped(
            state={},
            config={
                "configurable": {
                    "execution_guard": "invalid",
                },
            },
        )

    node.assert_not_called()


def test_invalid_node_rejected():

    with pytest.raises(
        TypeError,
        match="Graph node must be callable",
    ):

        GuardedGraphNode(
            node="invalid",
        )
