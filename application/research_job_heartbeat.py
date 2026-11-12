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

from persistence.research_job_repository import (
    ResearchJobLease,
    ResearchJobRepository,
)

from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ResearchJobLeaseLost(RuntimeError):
    """The research job lease can no longer be trusted."""


class ResearchJobHeartbeat:

    def __init__(
        self,
        session_factory,
        lease: ResearchJobLease,
        duration_seconds: int = 120,
        renewal_interval_seconds: float = 30.0,
    ):

        if (
            not isinstance(duration_seconds, int)
            or isinstance(duration_seconds, bool)
            or not 1 <= duration_seconds <= 86400
        ):
            raise ValueError(
                "duration_seconds must be an integer "
                "from 1 to 86400"
            )

        if (
            isinstance(renewal_interval_seconds, bool)
            or not isinstance(
                renewal_interval_seconds,
                (int, float),
            )
            or not 0 < renewal_interval_seconds < duration_seconds
        ):
            raise ValueError(
                "renewal_interval_seconds must be positive "
                "and less than duration_seconds"
            )

        self.session_factory = session_factory
        self.lease = lease
        self.duration_seconds = duration_seconds
        self.renewal_interval_seconds = renewal_interval_seconds

        self._stop_event = threading.Event()
        self._lost_event = threading.Event()

        self._thread = None
        self._failure = None

    def start(self) -> None:

        if self._thread is not None:

            raise RuntimeError(
                "Heartbeat has already been started."
            )

        self._thread = threading.Thread(
            target=self._run,
            name=(
                "research-job-heartbeat-"
                f"{self.lease.job_id}"
            ),
            daemon=True,
        )

        self._thread.start()

    def _run(self) -> None:

        while not self._stop_event.wait(
            self.renewal_interval_seconds
        ):

            try:

                with self.session_factory() as db:

                    renewed_lease = (
                        ResearchJobRepository(db).renew(
                            self.lease,
                            duration_seconds=self.duration_seconds,
                        )
                    )

                if renewed_lease is None:

                    self._failure = (
                        "Research job lease renewal was rejected."
                    )

                    self._lost_event.set()

                    logger.error(
                        "Research job lease ownership lost "
                        "for job %s",
                        self.lease.job_id,
                    )

                    return

                self.lease = renewed_lease

            except Exception as exc:

                self._failure = (
                    f"Research job lease renewal failed: {exc}"
                )

                self._lost_event.set()

                logger.exception(
                    "Research job lease renewal failed "
                    "for job %s",
                    self.lease.job_id,
                )

                return

    def check(self) -> None:

        if self._lost_event.is_set():

            raise ResearchJobLeaseLost(
                self._failure
                or "Research job lease ownership lost."
            )

        now = datetime.now(timezone.utc)

        expires_at = self.lease.expires_at

        if expires_at.tzinfo is None:

            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

        if now >= expires_at:

            raise ResearchJobLeaseLost(
                "Research job lease has expired."
            )

    
    def stop(self) -> None:

        self._stop_event.set()

        if self._thread is not None:

            self._thread.join()
