
from unittest.mock import MagicMock

import pytest

from application.execution_lease_heartbeat import (
    ExecutionLeaseLost,
)

from application.research_job_heartbeat import (
    ResearchJobLeaseLost,
)

from application.workflow_execution_guard import (
    WorkflowExecutionGuard,
)


def test_both_lease_checks_are_called():

    execution_check = MagicMock()
    job_check = MagicMock()

    guard = WorkflowExecutionGuard(
        execution_lease_check=execution_check,
        job_lease_check=job_check,
    )

    guard()

    execution_check.assert_called_once_with()
    job_check.assert_called_once_with()


def test_execution_lease_loss_propagates():

    execution_check = MagicMock(
        side_effect=ExecutionLeaseLost(
            "Execution lease lost."
        )
    )

    job_check = MagicMock()

    guard = WorkflowExecutionGuard(
        execution_lease_check=execution_check,
        job_lease_check=job_check,
    )

    with pytest.raises(
        ExecutionLeaseLost,
        match="Execution lease lost",
    ):

        guard()

    job_check.assert_not_called()


def test_job_lease_loss_propagates():

    execution_check = MagicMock()

    job_check = MagicMock(
        side_effect=ResearchJobLeaseLost(
            "Job lease lost."
        )
    )

    guard = WorkflowExecutionGuard(
        execution_lease_check=execution_check,
        job_lease_check=job_check,
    )

    with pytest.raises(
        ResearchJobLeaseLost,
        match="Job lease lost",
    ):

        guard()


def test_job_check_is_optional():

    execution_check = MagicMock()

    guard = WorkflowExecutionGuard(
        execution_lease_check=execution_check,
    )

    guard()

    execution_check.assert_called_once_with()


def test_invalid_execution_check_rejected():

    with pytest.raises(
        TypeError,
        match="Execution lease check must be callable",
    ):

        WorkflowExecutionGuard(
            execution_lease_check=None,
        )


def test_invalid_job_check_rejected():

    with pytest.raises(
        TypeError,
        match="Job lease check must be callable",
    ):

        WorkflowExecutionGuard(
            execution_lease_check=MagicMock(),
            job_lease_check="invalid",
        )
