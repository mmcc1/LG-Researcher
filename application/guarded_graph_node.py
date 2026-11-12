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

from langchain_core.runnables import (
    RunnableConfig,
)

from langgraph._internal._runnable import (
    RunnableCallable,
)


class GuardedGraphNode:

    def __init__(
        self,
        node: Callable,
    ):

        if not callable(node):

            raise TypeError(
                "Graph node must be callable."
            )

        self.node = RunnableCallable(
            node,
        )

    def __call__(
        self,
        state: dict,
        config: RunnableConfig,
    ) -> dict:

        configurable = config.get(
            "configurable",
            {},
        )

        execution_guard = configurable.get(
            "execution_guard"
        )

        if execution_guard is not None:

            if not callable(execution_guard):

                raise TypeError(
                    "Execution guard must be callable."
                )

            execution_guard()

        result = self.node.invoke(
            state,
            config=config,
        )

        if execution_guard is not None:
            execution_guard()

        return result
