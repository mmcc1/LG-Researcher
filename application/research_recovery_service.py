
import logging
import threading

from dataclasses import dataclass

from persistence.execution_lease_repository import (
    ExecutionLeaseUnavailable,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
    RecoveryNotEligible,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecoveryOutcome:

    session_id: str
    status: str
    error: str | None = None


class ResearchRecoveryService:
    """
    Discover abandoned workflows and request recovery.

    This service never acquires execution leases directly.

    Cancellation is cooperative and occurs between
    recovery sessions, never during an active workflow.
    """

    def __init__(
        self,
        workflow_service,
        session_factory,
    ):

        self.workflow_service = workflow_service
        self.session_factory = session_factory

    def find_candidates(
        self,
        limit: int = 100,
    ) -> list[str]:

        with self.session_factory() as db:

            repository = ResearchSessionRepository(db)

            return repository.find_recovery_candidates(
                limit=limit
            )

    def recover_session(
        self,
        session_id: str,
    ) -> RecoveryOutcome:

        try:

            result = self.workflow_service.recover(
                session_id
            )

            graph_result = result.graph_result

            paused = (
                isinstance(graph_result, dict)
                and graph_result.get(
                    "pause_requested"
                ) is True
            )

            return RecoveryOutcome(
                session_id=session_id,
                status=(
                    "paused"
                    if paused
                    else "resumed"
                ),
            )

        except (
            ExecutionLeaseUnavailable,
            RecoveryNotEligible,
        ):

            return RecoveryOutcome(
                session_id=session_id,
                status="skipped",
            )

        except Exception as exc:

            logger.exception(
                "Recovery failed for session %s",
                session_id,
            )

            return RecoveryOutcome(
                session_id=session_id,
                status="failed",
                error=str(exc),
            )

    def recover(
        self,
        limit: int = 100,
        cancellation_event: threading.Event | None = None,
    ) -> list[RecoveryOutcome]:

        if (
            cancellation_event is not None
            and cancellation_event.is_set()
        ):
            logger.info(
                "Recovery cancelled before candidate discovery."
            )
            return []

        candidates = self.find_candidates(
            limit=limit
        )

        outcomes = []

        for session_id in candidates:

            if (
                cancellation_event is not None
                and cancellation_event.is_set()
            ):

                logger.info(
                    "Recovery cancellation requested. "
                    "Stopping before the next session."
                )

                break

            outcomes.append(
                self.recover_session(
                    session_id
                )
            )

        return outcomes
