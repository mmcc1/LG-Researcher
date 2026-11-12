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

import json
import logging
import math
import os
import tempfile
import threading
import time

from datetime import datetime, timezone
from pathlib import Path

from application.research_recovery_worker import (
    RecoveryCycleSummary,
)


def utc_now() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()


class JsonLogFormatter(logging.Formatter):

    def format(self, record):

        payload = {
            "timestamp": utc_now(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if hasattr(record, "event"):

            payload["event"] = record.event

        if hasattr(record, "details"):

            payload["details"] = record.details

        if record.exc_info:

            payload["exception"] = (
                self.formatException(
                    record.exc_info
                )
            )

        return json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
        )


def configure_json_logging(
    level=logging.INFO,
):

    handler = logging.StreamHandler()

    handler.setFormatter(
        JsonLogFormatter()
    )

    root = logging.getLogger()

    root.handlers.clear()

    root.addHandler(
        handler
    )

    root.setLevel(
        level
    )


class RecoveryHealthMonitor:

    def __init__(
        self,
        health_path,
        logger=None,
    ):

        self.health_path = Path(
            health_path
        )

        self.logger = (
            logger
            or logging.getLogger(
                "research.recovery"
            )
        )

        self._lock = threading.Lock()

        self._state = {
            "state": "starting",
            "pid": os.getpid(),
            "started_at": utc_now(),
            "updated_at": utc_now(),
            "last_cycle_at": None,
            "last_success_at": None,
            "last_cycle_duration_seconds": None,
            "cycles": 0,
            "resumed": 0,
            "paused": 0,
            "skipped": 0,
            "failed_sessions": 0,
            "cycle_errors": 0,
            "last_error": None,
        }

    @property
    def snapshot(self):

        with self._lock:

            return dict(
                self._state
            )

    def _write_snapshot(self):

        self.health_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = json.dumps(
            self._state,
            indent=2,
            ensure_ascii=False,
        )

        temporary_name = None

        try:

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.health_path.parent,
                prefix=(
                    self.health_path.name + "."
                ),
                suffix=".tmp",
                delete=False,
            ) as temporary:

                temporary_name = temporary.name

                temporary.write(
                    payload
                )

                temporary.flush()

                os.fsync(
                    temporary.fileno()
                )

            os.replace(
                temporary_name,
                self.health_path,
            )

        finally:

            if (
                temporary_name is not None
                and os.path.exists(
                    temporary_name
                )
            ):

                os.unlink(
                    temporary_name
                )

    def _update(
        self,
        **values,
    ):

        with self._lock:

            self._state.update(
                values
            )

            self._state["updated_at"] = (
                utc_now()
            )

            self._write_snapshot()

    def started(self):

        self._update(
            state="running"
        )

        self.logger.info(
            "Recovery worker started.",
            extra={
                "event": "worker_started",
                "details": {
                    "pid": os.getpid(),
                },
            },
        )

    def cycle_started(self):

        self._update(
            state="recovering"
        )

        return time.perf_counter()

    def cycle_completed(
        self,
        summary: RecoveryCycleSummary,
        started_at: float,
    ):

        duration = (
            time.perf_counter()
            - started_at
        )

        now = utc_now()

        with self._lock:

            self._state["state"] = (
                "running"
            )

            self._state["cycles"] += 1

            self._state["resumed"] += (
                summary.resumed
            )

            self._state["paused"] += (
                summary.paused
            )

            self._state["skipped"] += (
                summary.skipped
            )

            self._state["failed_sessions"] += (
                summary.failed
            )

            self._state["last_cycle_at"] = now

            if summary.failed == 0:

                self._state[
                    "last_success_at"
                ] = now

            self._state[
                "last_cycle_duration_seconds"
            ] = round(
                duration,
                6,
            )

            self._state["updated_at"] = now

            self._write_snapshot()

            details = {
                "duration_seconds": round(
                    duration,
                    6,
                ),
                "scanned": summary.scanned,
                "resumed": summary.resumed,
                "paused": summary.paused,
                "skipped": summary.skipped,
                "failed": summary.failed,
            }

        self.logger.info(
            "Recovery cycle completed.",
            extra={
                "event": "recovery_cycle_completed",
                "details": details,
            },
        )

    def cycle_failed(
        self,
        error: Exception,
        started_at: float,
    ):

        duration = (
            time.perf_counter()
            - started_at
        )

        with self._lock:

            self._state["state"] = (
                "running"
            )

            self._state[
                "cycle_errors"
            ] += 1

            self._state[
                "last_error"
            ] = (
                f"{type(error).__name__}: {error}"
            )

            self._state[
                "last_cycle_at"
            ] = utc_now()

            self._state[
                "last_cycle_duration_seconds"
            ] = round(
                duration,
                6,
            )

            self._state[
                "updated_at"
            ] = utc_now()

            self._write_snapshot()

        self.logger.error(
            "Recovery cycle failed.",
            extra={
                "event": "recovery_cycle_failed",
                "details": {
                    "error": (
                        f"{type(error).__name__}: {error}"
                    ),
                    "duration_seconds": round(
                        duration,
                        6,
                    ),
                },
            },
        )

    def stopping(self):

        self._update(
            state="stopping"
        )

    def stopped(self):

        self._update(
            state="stopped"
        )

        self.logger.info(
            "Recovery worker stopped.",
            extra={
                "event": "worker_stopped",
                "details": {
                    "pid": os.getpid(),
                },
            },
        )
