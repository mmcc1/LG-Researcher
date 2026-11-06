
from collections.abc import Callable


class WorkflowExecutionGuard:

    def __init__(
        self,
        execution_lease_check: Callable[[], None],
        job_lease_check: Callable[[], None] | None = None,
    ):

        if not callable(execution_lease_check):

            raise TypeError(
                "Execution lease check must be callable."
            )

        if (
            job_lease_check is not None
            and not callable(job_lease_check)
        ):

            raise TypeError(
                "Job lease check must be callable."
            )

        self.execution_lease_check = execution_lease_check
        self.job_lease_check = job_lease_check

    def __call__(self) -> None:

        self.execution_lease_check()

        if self.job_lease_check is not None:
            self.job_lease_check()
