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
import os
import time
import uuid

from dataclasses import dataclass
from pathlib import Path


if os.name == "nt":
    import msvcrt
else:
    import fcntl


class HealthFileAlreadyOwned(RuntimeError):
    """Another worker holds the OS-backed lock."""


class HealthLockChanged(RuntimeError):
    """Compatibility exception for previous ownership API."""


@dataclass(frozen=True)
class HealthLockInfo:
    lock_path: Path
    pid: int
    token: str
    created_at_unix: float


def lock_path_for(health_path):

    health_path = Path(
        health_path
    ).resolve()

    return Path(
        str(health_path) + ".lock"
    )


def info_path_for(health_path):

    return Path(
        str(lock_path_for(health_path)) + ".info"
    )


def _lock_file(file):

    if os.name == "nt":

        file.seek(0)

        try:
            msvcrt.locking(
                file.fileno(),
                msvcrt.LK_NBLCK,
                1,
            )

        except OSError as exc:
            raise HealthFileAlreadyOwned(
                "Health-file lock is already held."
            ) from exc

    else:

        try:
            fcntl.flock(
                file.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )

        except BlockingIOError as exc:
            raise HealthFileAlreadyOwned(
                "Health-file lock is already held."
            ) from exc


def _unlock_file(file):

    if os.name == "nt":

        file.seek(0)

        msvcrt.locking(
            file.fileno(),
            msvcrt.LK_UNLCK,
            1,
        )

    else:

        fcntl.flock(
            file.fileno(),
            fcntl.LOCK_UN,
        )


def inspect_health_lock(health_path):
    """
    Read diagnostic metadata without accessing the
    operating-system lock target.

    Metadata may remain after an abrupt process exit.
    It does not prove that ownership is active.
    """

    path = info_path_for(
        health_path
    )

    try:

        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return HealthLockInfo(
            lock_path=lock_path_for(
                health_path
            ),
            pid=int(payload["pid"]),
            token=str(payload["token"]),
            created_at_unix=float(
                payload["created_at_unix"]
            ),
        )

    except (
        FileNotFoundError,
        OSError,
        UnicodeDecodeError,
        ValueError,
        KeyError,
        TypeError,
    ):

        return None


def clear_stale_health_lock(
    health_path,
    expected_token,
    *,
    owner_confirmed_stopped=False,
):
    """
    Legacy administrative API.

    OS-backed ownership automatically releases
    on process termination, so stale-lock deletion
    is no longer necessary.
    """

    raise RuntimeError(
        "Manual stale-lock deletion is no longer "
        "supported. The OS releases ownership "
        "when the process exits."
    )


class RecoveryHealthOwnership:

    def __init__(self, health_path):

        self.health_path = Path(
            health_path
        ).resolve()

        self.lock_path = lock_path_for(
            self.health_path
        )

        self.info_path = info_path_for(
            self.health_path
        )

        self._file = None
        self._token = None

    @property
    def token(self):
        return self._token

    def acquire(self):

        if self._file is not None:
            raise RuntimeError(
                "Health-file ownership already acquired."
            )

        self.lock_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file = open(
            self.lock_path,
            "a+b",
            buffering=0,
        )

        locked = False

        try:

            # Acquire the OS lock before changing any
            # ownership metadata. No sentinel write is needed.

            _lock_file(file)

            locked = True

            token = uuid.uuid4().hex

            metadata = {
                "pid": os.getpid(),
                "token": token,
                "created_at_unix": time.time(),
                "health_path": str(
                    self.health_path
                ),
            }

            # Write diagnostic metadata separately
            # from the locked file.

            temp_info = Path(
                str(self.info_path)
                + "."
                + token
                + ".tmp"
            )

            try:

                temp_info.write_text(
                    json.dumps(
                        metadata,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

                os.replace(
                    temp_info,
                    self.info_path,
                )

            finally:

                temp_info.unlink(
                    missing_ok=True
                )

            self._file = file
            self._token = token

        except BaseException:

            try:
                if locked:
                    _unlock_file(file)

            finally:
                file.close()

            raise

    def release(self):

        if self._file is None:
            return

        file = self._file
        token = self._token

        self._file = None
        self._token = None

        try:

            # Metadata cleanup is optional.
            # Do not remove metadata if it has
            # been replaced by another owner.

            info = inspect_health_lock(
                self.health_path
            )

            if (
                info is not None
                and info.token == token
            ):

                self.info_path.unlink(
                    missing_ok=True
                )

        finally:

            try:
                _unlock_file(file)

            finally:
                file.close()

    def __enter__(self):

        self.acquire()

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):

        self.release()
