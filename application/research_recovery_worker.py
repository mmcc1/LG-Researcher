
import threading

from dataclasses import dataclass
from typing import Callable

from application.research_recovery_service import (
    ResearchRecoveryService,
    RecoveryOutcome,
)


@dataclass(frozen=True)
class RecoveryCycleSummary:

    scanned: int

    resumed: int

    paused: int

    skipped: int

    failed: int

    outcomes: tuple[RecoveryOutcome, ...]

    @property
    def successful(self) -> bool:

        return self.failed == 0


class ResearchRecoveryWorker:

    def __init__(
        self,
        recovery_service: ResearchRecoveryService,
        output: Callable[[str], None] = print,
    ):

        self.recovery_service = recovery_service
        self.output = output

    def run_once(
        self,
        limit: int = 100,
        cancellation_event: threading.Event | None = None,
    ) -> RecoveryCycleSummary:

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 1000
        ):

            raise ValueError(
                "Recovery batch limit must be "
                "an integer between 1 and 1000."
            )

        self.output(
            "Starting operational recovery cycle..."
        )

        outcomes = tuple(
            self.recovery_service.recover(
                limit=limit,
                cancellation_event=cancellation_event,
            )
        )

        return self._summarize(
            outcomes
        )

    def run_session(
        self,
        session_id: str,
    ) -> RecoveryCycleSummary:

        if (
            not isinstance(session_id, str)
            or not session_id.strip()
        ):

            raise ValueError(
                "A research session ID is required."
            )

        session_id = session_id.strip()

        self.output(
            f"Starting targeted recovery: {session_id}"
        )

        outcome = (
            self.recovery_service.recover_session(
                session_id
            )
        )

        return self._summarize(
            (outcome,)
        )

    def _summarize(
        self,
        outcomes: tuple[RecoveryOutcome, ...],
    ) -> RecoveryCycleSummary:

        summary = RecoveryCycleSummary(
            scanned=len(outcomes),
            resumed=sum(
                item.status == "resumed"
                for item in outcomes
            ),
            paused=sum(
                item.status == "paused"
                for item in outcomes
            ),
            skipped=sum(
                item.status == "skipped"
                for item in outcomes
            ),
            failed=sum(
                item.status == "failed"
                for item in outcomes
            ),
            outcomes=outcomes,
        )

        for outcome in outcomes:

            message = (
                f"Session {outcome.session_id}: "
                f"{outcome.status}"
            )

            if outcome.error is not None:

                message += (
                    f" ({outcome.error})"
                )

            self.output(
                message
            )

        self.output(
            "Recovery cycle completed: "
            f"scanned={summary.scanned}, "
            f"resumed={summary.resumed}, "
            f"paused={summary.paused}, "
            f"skipped={summary.skipped}, "
            f"failed={summary.failed}"
        )

        return summary
