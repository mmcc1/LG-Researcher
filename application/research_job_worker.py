
import logging

from application.research_job_heartbeat import (
    ResearchJobHeartbeat,
    ResearchJobLeaseLost,
)

from persistence.research_job_repository import (
    ResearchJobLeaseUnavailable,
    ResearchJobRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)


logger = logging.getLogger(__name__)


class ResearchJobNotCompleted(RuntimeError):
    """The workflow returned without completing its session."""


class ResearchJobWorker:

    def __init__(
        self,
        session_factory,
        workflow_service,
        lease_duration_seconds: int = 120,
        heartbeat_interval_seconds: float = 30.0,
    ):

        self.session_factory = session_factory
        self.workflow_service = workflow_service

        self.lease_duration_seconds = (
            lease_duration_seconds
        )

        self.heartbeat_interval_seconds = (
            heartbeat_interval_seconds
        )

    def process_next(self) -> str | None:

        with self.session_factory() as db:

            repository = ResearchJobRepository(db)

            claimed = repository.claim_next(
                duration_seconds=self.lease_duration_seconds,
            )

        if claimed is None:

            return None

        logger.info(
            "Claimed research job %s",
            claimed.job_id,
        )

        heartbeat = ResearchJobHeartbeat(
            session_factory=self.session_factory,
            lease=claimed.lease,
            duration_seconds=self.lease_duration_seconds,
            renewal_interval_seconds=(
                self.heartbeat_interval_seconds
            ),
        )

        heartbeat.start()

        try:

            heartbeat.check()

            with self.session_factory() as db:

                repository = ResearchJobRepository(db)

                session_id = repository.associate_session(
                    heartbeat.lease
                )

            heartbeat.check()

            with self.session_factory() as db:

                session_repository = ResearchSessionRepository(db)

                research_session = session_repository.get(
                    session_id
                )

            if research_session is None:

                raise ValueError(
                    "Associated research session not found: "
                    f"{session_id}"
                )

            heartbeat.check()

            if research_session.status == "completed":

                logger.info(
                    "Research session %s is already completed. "
                    "Finalizing job %s without re-execution.",
                    session_id,
                    claimed.job_id,
                )

            else:

                try:

                    workflow_result = (
                        self.workflow_service.execute_existing(
                            session_id=session_id,
                            execution_guard=heartbeat.check,
                        )
                    )

                    graph_result = workflow_result.graph_result

                    paused = (
                        isinstance(graph_result, dict)
                        and graph_result.get("pause_requested") is True
                    )

                    if paused:

                        heartbeat.check()

                        with self.session_factory() as db:

                            repository = ResearchJobRepository(db)

                            pause_completed = (
                                repository.pause_claimed(
                                    heartbeat.lease
                                )
                            )

                        if pause_completed:

                            logger.info(
                                "Paused research job %s "
                                "with session %s",
                                claimed.job_id,
                                session_id,
                            )

                            return claimed.job_id
                                                
                        heartbeat.check()

                        raise ResearchJobNotCompleted(
                            "Research workflow returned after "
                            "a pause request, but the job "
                            "could not be transitioned to paused."
                        )

                except (
                    ResearchJobLeaseLost,
                    ResearchJobLeaseUnavailable,
                ):

                    raise

                except Exception as exc:

                    logger.exception(
                        "Research job %s execution failed.",
                        claimed.job_id,
                    )

                    heartbeat.check()

                    with self.session_factory() as db:

                        repository = ResearchJobRepository(db)

                        failed = repository.fail(
                            lease=heartbeat.lease,
                            error=str(exc) or type(exc).__name__,
                        )

                    if not failed:

                        logger.warning(
                            "Could not mark research job %s "
                            "as failed; ownership may have changed.",
                            claimed.job_id,
                        )

                    raise

            heartbeat.check()

            with self.session_factory() as db:

                repository = ResearchJobRepository(db)

                completed = repository.complete(
                    heartbeat.lease
                )

            if not completed:

                heartbeat.check()

                raise ResearchJobNotCompleted(
                    "Research job could not be finalized. "
                    "The session may be unfinished or "
                    "job ownership may have changed."
                )

            logger.info(
                "Completed research job %s "
                "with session %s",
                claimed.job_id,
                session_id,
            )

            return claimed.job_id

        finally:

            heartbeat.stop()
