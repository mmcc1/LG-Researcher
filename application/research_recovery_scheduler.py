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
import math
import threading
import time

from dataclasses import dataclass
from typing import Callable

from application.research_recovery_worker import (
    ResearchRecoveryWorker,
    RecoveryCycleSummary,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecoverySchedulerStatistics:

    cycles: int
    resumed: int
    paused: int
    skipped: int
    failed: int
    cycle_errors: int
    monitor_errors: int = 0


class ResearchRecoveryScheduler:

    def __init__(
        self,
        worker: ResearchRecoveryWorker,
        interval_seconds: float = 30.0,
        batch_limit: int = 25,
        on_cycle: Callable[
            [RecoveryCycleSummary], None
        ] | None = None,
        on_cycle_start: Callable[
            [], None
        ] | None = None,
        on_cycle_error: Callable[
            [Exception], None
        ] | None = None,
    ):

        if (
            isinstance(interval_seconds, bool)
            or not isinstance(
                interval_seconds,
                (int, float),
            )
            or not math.isfinite(interval_seconds)
            or not 0.1 <= interval_seconds <= 86400
        ):
            raise ValueError(
                "Polling interval must be between "
                "0.1 and 86400 seconds."
            )

        if (
            isinstance(batch_limit, bool)
            or not isinstance(batch_limit, int)
            or not 1 <= batch_limit <= 1000
        ):
            raise ValueError(
                "Batch limit must be an integer "
                "between 1 and 1000."
            )

        self.worker = worker

        self.interval_seconds = float(
            interval_seconds
        )

        self.batch_limit = batch_limit

        self.on_cycle = on_cycle
        self.on_cycle_start = on_cycle_start
        self.on_cycle_error = on_cycle_error

        self._stop_event = threading.Event()

        self._run_lock = threading.Lock()
        self._statistics_lock = threading.Lock()

        self._cycles = 0
        self._resumed = 0
        self._paused = 0
        self._skipped = 0
        self._failed = 0
        self._cycle_errors = 0
        self._monitor_errors = 0

    def request_stop(self):

        self._stop_event.set()

    @property
    def stop_requested(self) -> bool:

        return self._stop_event.is_set()

    @property
    def cancellation_event(self) -> threading.Event:

        return self._stop_event

    @property
    def statistics(self) -> RecoverySchedulerStatistics:

        with self._statistics_lock:

            return RecoverySchedulerStatistics(
                cycles=self._cycles,
                resumed=self._resumed,
                paused=self._paused,
                skipped=self._skipped,
                failed=self._failed,
                cycle_errors=self._cycle_errors,
                monitor_errors=self._monitor_errors,
            )

    def run_forever(self) -> RecoverySchedulerStatistics:

        if not self._run_lock.acquire(
            blocking=False
        ):
            raise RuntimeError(
                "Recovery scheduler is already running."
            )

        try:

            logger.info(
                "Recovery scheduler started: "
                "interval=%s seconds, batch_limit=%s",
                self.interval_seconds,
                self.batch_limit,
            )

            while not self._stop_event.is_set():

                self._notify_monitor(
                    self.on_cycle_start
                )

                if self._stop_event.is_set():
                    break

                try:

                    summary = self.worker.run_once(
                        limit=self.batch_limit,
                        cancellation_event=self._stop_event,
                    )

                except Exception as exc:

                    logger.exception(
                        "Recovery scheduler cycle failed."
                    )

                    with self._statistics_lock:
                        self._cycle_errors += 1

                    self._notify_monitor(
                        self.on_cycle_error,
                        exc,
                    )

                else:

                    with self._statistics_lock:
                        self._cycles += 1
                        self._resumed += summary.resumed
                        self._paused += summary.paused
                        self._skipped += summary.skipped
                        self._failed += summary.failed

                    self._notify_monitor(
                        self.on_cycle,
                        summary,
                    )

                # Do not wait for another polling interval
                # after shutdown has been requested.

                if self._stop_event.is_set():
                    break

                deadline = (
                    time.monotonic()
                    + self.interval_seconds
                )

                while not self._stop_event.is_set():

                    remaining = (
                        deadline - time.monotonic()
                    )

                    if remaining <= 0:
                        break

                    if self._stop_event.wait(
                        timeout=min(remaining, 0.2)
                    ):
                        break

            logger.info(
                "Recovery scheduler stopped."
            )

            return self.statistics

        finally:

            self._run_lock.release()

    def _notify_monitor(self, callback, *args):

        if callback is None:
            return

        try:

            callback(*args)

        except Exception:

            with self._statistics_lock:
                self._monitor_errors += 1

            logger.exception(
                "Recovery monitoring callback failed."
            )
