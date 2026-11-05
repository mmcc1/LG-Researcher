
import logging
import sys

from collections.abc import Callable

from domain.workflow import ResearchWorkflowResult

from application.execution_lease_heartbeat import (
    ExecutionLeaseHeartbeat,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
    RecoveryNotEligible,
)


logger = logging.getLogger(__name__)


class ResearchWorkflowService:

    def __init__(
        self,
        graph,
        session_factory,
        lease_duration_seconds: int = 120,
        heartbeat_interval_seconds: float = 30.0,
    ):

        if (
            not isinstance(lease_duration_seconds, int)
            or isinstance(lease_duration_seconds, bool)
            or not 1 <= lease_duration_seconds <= 86400
        ):
            raise ValueError(
                "lease_duration_seconds must be an integer "
                "from 1 to 86400"
            )

        if (
            isinstance(heartbeat_interval_seconds, bool)
            or not isinstance(
                heartbeat_interval_seconds,
                (int, float),
            )
            or not 0 < heartbeat_interval_seconds < lease_duration_seconds
        ):
            raise ValueError(
                "heartbeat_interval_seconds must be positive "
                "and less than lease_duration_seconds"
            )

        self.graph = graph
        self.session_factory = session_factory
        self.lease_duration_seconds = lease_duration_seconds
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

    def start(
        self,
        topic: str,
        scope: str | None = None,
    ) -> ResearchWorkflowResult:

        return self._start(
            topic=topic,
            scope=scope,
            execution_target="complete",
        )

    def start_research(
        self,
        topic: str,
        scope: str | None = None,
    ) -> ResearchWorkflowResult:

        return self._start(
            topic=topic,
            scope=scope,
            execution_target="research",
        )

    def _start(
        self,
        topic: str,
        scope: str | None,
        execution_target: str,
    ) -> ResearchWorkflowResult:

        topic = topic.strip()

        if not topic:
            raise ValueError(
                "A research topic is required."
            )

        if scope is not None:

            scope = scope.strip()

            if not scope:
                scope = None

        with self.session_factory() as db:

            repository = ResearchSessionRepository(db)

            research_session = repository.create(
                topic=topic,
                scope=scope,
            )

            # Ownership must be acquired before entering planning.

            session_id = research_session.id
            session_topic = research_session.topic
            session_scope = research_session.scope

        return self._execute_with_lease(
            session_id=session_id,
            topic=session_topic,
            scope=session_scope,
            resume=False,
            execution_target=execution_target,
        )

    def resume(
        self,
        session_id: str,
    ) -> ResearchWorkflowResult:

        return self._resume(
            session_id=session_id,
            execution_target="complete",
        )

    def resume_research(
        self,
        session_id: str,
    ) -> ResearchWorkflowResult:

        return self._resume(
            session_id=session_id,
            execution_target="research",
        )

    def recover(
        self,
        session_id: str,
    ) -> ResearchWorkflowResult:
        """
        Resume an abandoned session only if it remains
        eligible for automatic recovery.

        Unlike explicit resume(), this operation respects
        the recovery status policy and pause_requested.
        """

        if not isinstance(session_id, str):

            raise ValueError(
                "A research session ID is required."
            )

        session_id = session_id.strip()

        if not session_id:

            raise ValueError(
                "A research session ID is required."
            )

        with self.session_factory() as db:

            repository = ResearchSessionRepository(db)

            research_session = repository.get(
                session_id
            )

            if research_session is None:

                raise RecoveryNotEligible(
                    "Research session not found: "
                    f"{session_id}"
                )

            topic = research_session.topic
            scope = research_session.scope

        # Eligibility is checked again under the execution
        # lease by the fenced repository method.

        return self._execute_with_lease(
            session_id=session_id,
            topic=topic,
            scope=scope,
            resume=True,
            execution_target="complete",
            recovery=True,
        )

    def _resume(
        self,
        session_id: str,
        execution_target: str,
    ) -> ResearchWorkflowResult:

        session_id = session_id.strip()

        if not session_id:

            raise ValueError(
                "A research session ID is required."
            )

        # Preserve the existing early checks and messages.
        # The authoritative lifecycle check follows lease acquisition.

        with self.session_factory() as db:

            repository = ResearchSessionRepository(db)

            research_session = repository.get(
                session_id
            )

            if research_session is None:

                raise ValueError(
                    "Research session not found."
                )

            if research_session.status == "completed":

                raise ValueError(
                    "This research session has already been completed."
                )

            session_topic = research_session.topic
            session_scope = research_session.scope

        return self._execute_with_lease(
            session_id=session_id,
            topic=session_topic,
            scope=session_scope,
            resume=True,
            execution_target=execution_target,
        )

    def execute_existing(
        self,
        session_id: str,
        execution_guard: Callable[[], None] | None = None,
    ) -> ResearchWorkflowResult:

        if not isinstance(session_id, str):

            raise ValueError(
                "A research session ID is required."
            )

        session_id = session_id.strip()

        if not session_id:

            raise ValueError(
                "A research session ID is required."
            )

        with self.session_factory() as db:

            repository = ResearchSessionRepository(db)

            research_session = repository.get(
                session_id
            )

            if research_session is None:

                raise ValueError(
                    "Research session not found."
                )

            status = research_session.status
            topic = research_session.topic
            scope = research_session.scope

        if status == "completed":

            raise RecoveryNotEligible(
                "This research session has already been completed."
            )

        if status == "created":

            return self._execute_with_lease(
                session_id=session_id,
                topic=topic,
                scope=scope,
                resume=False,
                execution_target="complete",
                execution_guard=execution_guard,
            )

        if status in {
            "planning",
            "planned",
            "researching",
            "researched",
            "reviewing",
            "reviewed",
            "reporting",
        }:

            return self._execute_with_lease(
                session_id=session_id,
                topic=topic,
                scope=scope,
                resume=True,
                execution_target="complete",
                recovery=True,
                execution_guard=execution_guard,
            )

        raise RecoveryNotEligible(
            "Research session is not eligible "
            f"for job execution: {status}"
        )

    def _execute_with_lease(
        self,
        session_id: str,
        topic: str,
        scope: str | None,
        resume: bool,
        execution_target: str,
        recovery: bool = False,
        execution_guard: Callable[[], None] | None = None,
    ) -> ResearchWorkflowResult:

        if execution_target not in {
            "complete",
            "research",
        }:

            raise ValueError(
                "Unsupported research workflow execution target: "
                f"{execution_target}"
            )

        with self.session_factory() as db:

            lease = ExecutionLeaseRepository(db).acquire(
                session_id,
                duration_seconds=self.lease_duration_seconds,
            )

        try:

            if execution_guard is not None:
                execution_guard()

            with self.session_factory() as db:

                repository = ResearchSessionRepository(db)

                if recovery:

                    if not resume:

                        raise ValueError(
                            "Automatic recovery requires "
                            "resume=True."
                        )

                    if execution_target != "complete":

                        raise ValueError(
                            "Automatic recovery requires "
                            "execution_target='complete'."
                        )

                    topic, scope = (
                        repository.prepare_recovery_execution_fenced(
                            session_id=session_id,
                            lease=lease,
                        )
                    )

                else:

                    topic, scope = (
                        repository.prepare_execution_fenced(
                            session_id=session_id,
                            lease=lease,
                            resume=resume,
                        )
                    )

            # The job lease may have been lost while the
            # fenced preparation transaction was running.

            if execution_guard is not None:
                execution_guard()

            heartbeat = ExecutionLeaseHeartbeat(
                session_factory=self.session_factory,
                lease=lease,
                duration_seconds=self.lease_duration_seconds,
                renewal_interval_seconds=self.heartbeat_interval_seconds,
            )

            heartbeat.start()

            try:

                return self._execute(
                    session_id=session_id,
                    topic=topic,
                    scope=scope,
                    resume=resume,
                    execution_target=execution_target,
                    lease=lease,
                    execution_guard=execution_guard,
                )

            finally:

                original_exception_active = (
                    sys.exc_info()[0] is not None
                )

                try:

                    heartbeat.stop()

                except Exception:

                    if original_exception_active:

                        logger.exception(
                            "Heartbeat shutdown failed for "
                            "session %s; preserving original error",
                            session_id,
                        )

                    else:

                        raise

        finally:

            original_exception_active = (
                sys.exc_info()[0] is not None
            )

            try:

                with self.session_factory() as db:

                    released = (
                        ExecutionLeaseRepository(db).release(
                            lease
                        )
                    )

                if not released:

                    raise RuntimeError(
                        "Execution lease no longer owned "
                        f"by this execution: {session_id}"
                    )

            except Exception:

                if original_exception_active:

                    logger.exception(
                        "Lease cleanup failed for session %s; "
                        "preserving original error",
                        session_id,
                    )

                else:

                    raise

    def _execute(
        self,
        session_id: str,
        topic: str,
        scope: str | None,
        resume: bool,
        execution_target: str,
        lease: ExecutionLease,
        execution_guard: Callable[[], None] | None = None,
    ) -> ResearchWorkflowResult:

        if execution_target not in {
            "complete",
            "research",
        }:

            raise ValueError(
                "Unsupported research workflow execution target: "
                f"{execution_target}"
            )

        initial_state = {
            "session_id": session_id,
            "topic": topic,
            "scope": scope,
            "resume": resume,
            "resume_phase": None,
            "execution_target": execution_target,
            "pause_requested": False,
            "research_plan": None,
            "current_question_id": None,
            "current_question": None,
            "search_plan": None,
            "current_search_attempt_id": None,
            "search_results": [],
            "current_review_question_id": None,
            "current_review_question": None,
            "search_required": False,
        }

        if execution_guard is not None:
            execution_guard()

        graph_result = self.graph.invoke(
            initial_state,
            config={
                "configurable": {
                    "execution_lease": lease,
                    "execution_guard": execution_guard,
                },
            },
        )

        if execution_guard is not None:
            execution_guard()

        return ResearchWorkflowResult(
            session_id=session_id,
            topic=topic,
            graph_result=graph_result,
        )
