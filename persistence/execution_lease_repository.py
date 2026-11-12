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

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


class ExecutionLeaseUnavailable(RuntimeError):
    """A research session does not have an acquirable execution lease."""

class ExecutionLeaseFenceRejected(RuntimeError):
    """The execution does not hold a valid lease."""


@dataclass(frozen=True)
class ExecutionLease:
    session_id: str
    owner: str
    version: int
    expires_at: datetime  # UTC, returned by SQL Server


class ExecutionLeaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def acquire(self, session_id: str, duration_seconds: int = 120) -> ExecutionLease:
        if not session_id or not session_id.strip():
            raise ValueError("session_id is required")
        if not isinstance(duration_seconds, int) or isinstance(duration_seconds, bool) or duration_seconds < 1:
            raise ValueError("duration_seconds must be a positive integer")
        if duration_seconds > 86400:
            raise ValueError("duration_seconds cannot exceed 86400")

        owner = str(uuid4())
        # SQL Server serializes competing updates of the same row. OUTPUT returns
        # the winning version and server-computed expiry in the same statement.
        statement = text("""
            UPDATE dbo.research_sessions
            SET execution_owner = :owner,
                execution_lease_expires_at = DATEADD(
                    second, :duration_seconds, SYSUTCDATETIME()
                ),
                execution_lease_version = execution_lease_version + 1
            OUTPUT INSERTED.execution_lease_version,
                   INSERTED.execution_lease_expires_at
            WHERE id = :session_id
              AND (
                    execution_owner IS NULL
                    OR execution_lease_expires_at IS NULL
                    OR execution_lease_expires_at <= SYSUTCDATETIME()
                  )
        """)
        try:
            row = self.db.execute(statement, {
                "owner": owner,
                "duration_seconds": duration_seconds,
                "session_id": session_id.strip(),
            }).first()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        if row is None:
            raise ExecutionLeaseUnavailable(
                f"Session {session_id} does not exist or has an active execution lease"
            )
        return ExecutionLease(
            session_id=session_id.strip(),
            owner=owner,
            version=int(row[0]),
            expires_at=row[1],
        )

    def release(self, lease: ExecutionLease) -> bool:
        """Release only when both owner and fencing version still match."""
        statement = text("""
            UPDATE dbo.research_sessions
            SET execution_owner = NULL,
                execution_lease_expires_at = NULL
            OUTPUT INSERTED.id
            WHERE id = :session_id
              AND execution_owner = :owner
              AND execution_lease_version = :version
        """)
        try:
            row = self.db.execute(statement, {
                "session_id": lease.session_id,
                "owner": lease.owner,
                "version": lease.version,
            }).first()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return row is not None


    def renew(
        self,
        lease: ExecutionLease,
        duration_seconds: int = 120,
    ) -> ExecutionLease | None:

        if (
            not isinstance(duration_seconds, int)
            or isinstance(duration_seconds, bool)
            or not 1 <= duration_seconds <= 86400
        ):
            raise ValueError(
                "duration_seconds must be an integer "
                "from 1 to 86400"
            )

        statement = text("""
            UPDATE dbo.research_sessions
            SET execution_lease_expires_at = DATEADD(
                second,
                :duration_seconds,
                SYSUTCDATETIME()
            )
            OUTPUT INSERTED.execution_lease_expires_at
            WHERE id = :session_id
              AND execution_owner = :owner
              AND execution_lease_version = :version
              AND execution_lease_expires_at > SYSUTCDATETIME()
        """)

        try:

            row = self.db.execute(
                statement,
                {
                    "session_id": lease.session_id,
                    "owner": lease.owner,
                    "version": lease.version,
                    "duration_seconds": duration_seconds,
                },
            ).first()

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        if row is None:
            return None

        return ExecutionLease(
            session_id=lease.session_id,
            owner=lease.owner,
            version=lease.version,
            expires_at=row[0],
        )

    
    def fence(
        self,
        lease: ExecutionLease,
    ) -> None:

        statement = text("""
            SELECT id
            FROM dbo.research_sessions WITH (
                UPDLOCK,
                HOLDLOCK
            )
            WHERE id = :session_id
              AND execution_owner = :owner
              AND execution_lease_version = :version
              AND execution_lease_expires_at > SYSUTCDATETIME()
        """)

        try:

            row = self.db.execute(
                statement,
                {
                    "session_id": lease.session_id,
                    "owner": lease.owner,
                    "version": lease.version,
                },
            ).first()

            if row is None:

                raise ExecutionLeaseFenceRejected(
                    "Execution lease fencing rejected "
                    f"for session {lease.session_id}"
                )

        except Exception:

            self.db.rollback()
            raise
