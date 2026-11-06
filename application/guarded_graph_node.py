
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
