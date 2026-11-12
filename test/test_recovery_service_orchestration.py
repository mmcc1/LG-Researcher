from unittest.mock import MagicMock, patch

from application.research_recovery_service import (
    ResearchRecoveryService,
)


def main() -> None:

    workflow_service = MagicMock()
    session_factory = MagicMock()

    service = ResearchRecoveryService(
        workflow_service=workflow_service,
        session_factory=session_factory,
    )

    call_order = []

    def reconcile_completed(limit: int) -> int:

        call_order.append("completed")

        return 0

    def reconcile_pauses(limit: int) -> int:

        call_order.append("pauses")

        return 0

    def find_candidates(limit: int) -> list[str]:

        call_order.append("candidates")

        return []

    with patch.object(
        service,
        "reconcile_completed_jobs",
        side_effect=reconcile_completed,
    ), patch.object(
        service,
        "reconcile_abandoned_pauses",
        side_effect=reconcile_pauses,
    ), patch.object(
        service,
        "find_candidates",
        side_effect=find_candidates,
    ):

        outcomes = service.recover(
            limit=100,
        )

    assert outcomes == []

    assert call_order == [
        "completed",
        "pauses",
        "candidates",
    ], (
        "Recovery operations executed in an unexpected order: "
        f"{call_order}"
    )

    print(
        "Recovery reconciliation ordering: PASSED"
    )

    print(
        "Recovery-service orchestration: PASSED"
    )


if __name__ == "__main__":

    main()