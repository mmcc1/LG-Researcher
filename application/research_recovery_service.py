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

from persistence.research_job_repository import (
    ResearchJobRepository,
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

            if not paused:

                with self.session_factory() as db:

                    session_repository = ResearchSessionRepository(
                        db
                    )

                    research_session = session_repository.get(
                        session_id
                    )

                if (
                    research_session is not None
                    and research_session.status == "completed"
                ):

                    with self.session_factory() as db:

                        job_repository = ResearchJobRepository(
                            db
                        )

                        reconciled = (
                            job_repository.reconcile_completed_session(
                                session_id=session_id,
                            )
                        )

                    if reconciled:

                        logger.info(
                            "Reconciled completed research session %s "
                            "with its associated research job.",
                            session_id,
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

    def reconcile_completed_jobs(
        self,
        limit: int = 100,
    ) -> int:

        with self.session_factory() as db:

            repository = ResearchJobRepository(
                db
            )

            reconciled_count = (
                repository.reconcile_completed_jobs(
                    limit=limit,
                )
            )

        if reconciled_count > 0:

            logger.info(
                "Reconciled %d completed research jobs.",
                reconciled_count,
            )

        return reconciled_count


    def reconcile_abandoned_pauses(
        self,
        limit: int = 100,
    ) -> int:

        with self.session_factory() as db:

            repository = ResearchJobRepository(db)

            reconciled_count = (
                repository.reconcile_abandoned_pauses(
                    limit=limit,
                )
            )

        if reconciled_count > 0:

            logger.info(
                "Reconciled %d abandoned research "
                "job pause requests.",
                reconciled_count,
            )

        return reconciled_count
    

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

        self.reconcile_completed_jobs(
            limit=limit,
        )

        self.reconcile_abandoned_pauses(
            limit=limit
        )

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
