#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

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
