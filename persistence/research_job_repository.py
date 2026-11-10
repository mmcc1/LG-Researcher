
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from persistence.models import (
    ResearchJob,
    ResearchJobQuestion,
    ResearchSession,
)


class ResearchJobLeaseUnavailable(RuntimeError):
    """The job is not owned by the requested execution."""


@dataclass(frozen=True)
class ResearchJobLease:

    job_id: str
    owner: str
    version: int
    expires_at: datetime


@dataclass(frozen=True)
class ClaimedResearchJob:

    job_id: str
    user_id: str
    topic: str
    scope: str | None
    research_session_id: str | None
    lease: ResearchJobLease


@dataclass(frozen=True)
class ResearchJobQuestionRecord:

    id: int
    research_job_id: str
    question: str
    created_at: datetime


class ResearchJobRepository:

    def __init__(self, db: Session):

        self.db = db

    @staticmethod
    def _validate_duration(duration_seconds: int) -> None:

        if (
            not isinstance(duration_seconds, int)
            or isinstance(duration_seconds, bool)
            or not 1 <= duration_seconds <= 86400
        ):
            raise ValueError(
                "duration_seconds must be an integer "
                "from 1 to 86400"
            )



    def create_draft(
        self,
        user_id: str,
        topic: str,
        scope: str | None = None,
    ) -> str:

        if not user_id or not user_id.strip():
            raise ValueError("user_id is required")

        if not topic or not topic.strip():
            raise ValueError("topic is required")

        user_id = user_id.strip()
        topic = topic.strip()

        if len(topic) > 1000:
            raise ValueError(
                "topic cannot exceed 1000 characters"
            )

        if scope is not None:
            scope = scope.strip() or None

        job_id = str(uuid4())

        now = datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )

        job = ResearchJob(
            id=job_id,
            user_id=user_id,
            research_session_id=None,
            topic=topic,
            scope=scope,
            status="draft",
            created_at=now,
            submitted_at=None,
            started_at=None,
            completed_at=None,
            last_error=None,
            execution_owner=None,
            lease_expires_at=None,
            lease_version=0,
        )

        try:

            self.db.add(job)
            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        return job_id


    def update_draft(
        self,
        job_id: str,
        user_id: str,
        topic: str,
        scope: str | None,
    ) -> bool:

        if not topic or not topic.strip():
            raise ValueError("topic is required")

        topic = topic.strip()

        if len(topic) > 1000:
            raise ValueError(
                "topic cannot exceed 1000 characters"
            )

        if scope is not None:
            scope = scope.strip() or None

        statement = text("""
            UPDATE dbo.research_jobs
            SET topic = :topic,
                scope = :scope
            OUTPUT INSERTED.id
            WHERE id = :job_id
              AND user_id = :user_id
              AND status = 'draft'
              AND research_session_id IS NULL
        """)

        try:

            row = self.db.execute(
                statement,
                {
                    "job_id": job_id,
                    "user_id": user_id,
                    "topic": topic,
                    "scope": scope,
                },
            ).first()

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        return row is not None


    def submit_draft(
        self,
        job_id: str,
        user_id: str,
    ) -> bool:

        statement = text("""
            UPDATE dbo.research_jobs
            SET status = 'queued',
                submitted_at = SYSUTCDATETIME()
            OUTPUT INSERTED.id
            WHERE id = :job_id
              AND user_id = :user_id
              AND status = 'draft'
              AND research_session_id IS NULL
              AND submitted_at IS NULL
        """)

        try:

            row = self.db.execute(
                statement,
                {
                    "job_id": job_id,
                    "user_id": user_id,
                },
            ).first()

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        return row is not None

    
    
    def add_draft_question(
        self,
        job_id: str,
        user_id: str,
        question: str,
    ) -> int | None:

        if not question or not question.strip():
            raise ValueError("question is required")

        question = question.strip()

        if len(question) > 2000:
            raise ValueError(
                "question cannot exceed 2000 characters"
            )

        try:

            # Acquire the parent job lock using its primary key.
            # Keep the lock until the insertion commits.
            statement = text("""
                SELECT
                    id,
                    user_id,
                    status,
                    research_session_id,
                    submitted_at
                FROM dbo.research_jobs WITH (
                    UPDLOCK,
                    HOLDLOCK
                )
                WHERE id = :job_id
            """)

            row = self.db.execute(
                statement,
                {
                    "job_id": job_id,
                },
            ).first()

            if (
                row is None
                or row[1] != user_id
                or row[2] != "draft"
                or row[3] is not None
                or row[4] is not None
            ):

                self.db.rollback()
                return None

            now = datetime.now(
                timezone.utc
            ).replace(
                tzinfo=None
            )

            draft_question = ResearchJobQuestion(
                research_job_id=job_id,
                question=question,
                created_at=now,
            )

            self.db.add(draft_question)
            self.db.flush()

            question_id = draft_question.id

            self.db.commit()

            return question_id

        except Exception:

            self.db.rollback()
            raise


        
    def remove_draft_question(
        self,
        job_id: str,
        user_id: str,
        question_id: int,
    ) -> bool:

        try:

            # Serialize question deletion against job submission.
            statement = text("""
                SELECT
                    id,
                    user_id,
                    status,
                    research_session_id,
                    submitted_at
                FROM dbo.research_jobs WITH (
                    UPDLOCK,
                    HOLDLOCK
                )
                WHERE id = :job_id
            """)

            row = self.db.execute(
                statement,
                {
                    "job_id": job_id,
                },
            ).first()

            if (
                row is None
                or row[1] != user_id
                or row[2] != "draft"
                or row[3] is not None
                or row[4] is not None
            ):

                self.db.rollback()
                return False

            delete_statement = text("""
                DELETE FROM dbo.research_job_questions
                OUTPUT DELETED.id
                WHERE id = :question_id
                  AND research_job_id = :job_id
            """)

            deleted_row = self.db.execute(
                delete_statement,
                {
                    "question_id": question_id,
                    "job_id": job_id,
                },
            ).first()

            self.db.commit()

            return deleted_row is not None

        except Exception:

            self.db.rollback()
            raise



    def list_draft_questions(
        self,
        job_id: str,
        user_id: str,
    ) -> list[ResearchJobQuestionRecord]:

        statement = text("""
            SELECT
                q.id,
                q.research_job_id,
                q.question,
                q.created_at
            FROM dbo.research_job_questions AS q
            INNER JOIN dbo.research_jobs AS j
                ON j.id = q.research_job_id
            WHERE j.id = :job_id
              AND j.user_id = :user_id
            ORDER BY q.id
        """)

        try:

            rows = self.db.execute(
                statement,
                {
                    "job_id": job_id,
                    "user_id": user_id,
                },
            ).all()

            questions = []

            for row in rows:

                record = ResearchJobQuestionRecord(
                    id=int(row[0]),
                    research_job_id=row[1],
                    question=row[2],
                    created_at=row[3],
                )

                questions.append(record)

            self.db.commit()

            return questions

        except Exception:

            self.db.rollback()
            raise

    
    def list_session_job_questions(
        self,
        session_id: str,
    ) -> list[str]:

        statement = text("""
            SELECT
                q.question
            FROM dbo.research_job_questions AS q
            INNER JOIN dbo.research_jobs AS j
                ON j.id = q.research_job_id
            WHERE j.research_session_id = :session_id
            ORDER BY q.id
        """)

        try:

            rows = self.db.execute(
                statement,
                {
                    "session_id": session_id,
                },
            ).all()

            questions = [
                row[0]
                for row in rows
            ]

            self.db.commit()

            return questions

        except Exception:

            self.db.rollback()
            raise



    def submit(
        self,
        user_id: str,
        topic: str,
        scope: str | None = None,
    ) -> str:

        if not user_id or not user_id.strip():
            raise ValueError("user_id is required")

        if not topic or not topic.strip():
            raise ValueError("topic is required")

        user_id = user_id.strip()
        topic = topic.strip()

        if len(topic) > 1000:
            raise ValueError(
                "topic cannot exceed 1000 characters"
            )

        if scope is not None:
            scope = scope.strip() or None

        job_id = str(uuid4())

        now = datetime.now(timezone.utc).replace(
            tzinfo=None
        )

        job = ResearchJob(
            id=job_id,
            user_id=user_id,
            research_session_id=None,
            topic=topic,
            scope=scope,
            status="queued",
            created_at=now,
            submitted_at=now,
            started_at=None,
            completed_at=None,
            last_error=None,
            execution_owner=None,
            lease_expires_at=None,
            lease_version=0,
        )

        try:

            self.db.add(job)
            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        return job_id

    def claim_next(
        self,
        duration_seconds: int = 120,
    ) -> ClaimedResearchJob | None:

        self._validate_duration(duration_seconds)

        owner = str(uuid4())

        # UPDLOCK reserves the selected row for this transaction.
        # READPAST lets another worker skip a locked row.
        # The update and ownership assignment are one statement.
        statement = text("""
            ;WITH next_job AS (
                SELECT TOP (1)
                    id,
                    user_id,
                    topic,
                    scope,
                    research_session_id,
                    status,
                    execution_owner,
                    lease_expires_at,
                    lease_version,
                    started_at
                FROM dbo.research_jobs WITH (
                    UPDLOCK,
                    READPAST,
                    ROWLOCK
                )
                WHERE (
                    status = 'queued'
                    OR (
                        status = 'claimed'
                        AND lease_expires_at <= SYSUTCDATETIME()
                    )
                )
                AND (
                    research_session_id IS NULL
                    OR NOT EXISTS (
                        SELECT 1
                        FROM dbo.research_sessions AS s
                        WHERE s.id = research_session_id
                        AND (
                            s.status = 'completed'
                            OR s.pause_requested = 1
                            OR (
                                s.execution_owner IS NOT NULL
                                AND s.execution_lease_expires_at > SYSUTCDATETIME()
                            )
                        )
                    )
                )
                ORDER BY submitted_at, id
            )
            UPDATE next_job
            SET status = 'claimed',
                execution_owner = :owner,
                lease_expires_at = DATEADD(
                    second,
                    :duration_seconds,
                    SYSUTCDATETIME()
                ),
                lease_version = lease_version + 1
            OUTPUT
                INSERTED.id,
                INSERTED.user_id,
                INSERTED.topic,
                INSERTED.scope,
                INSERTED.research_session_id,
                INSERTED.lease_version,
                INSERTED.lease_expires_at
        """)

        try:

            row = self.db.execute(
                statement,
                {
                    "owner": owner,
                    "duration_seconds": duration_seconds,
                },
            ).first()

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        if row is None:
            return None

        lease = ResearchJobLease(
            job_id=row[0],
            owner=owner,
            version=int(row[5]),
            expires_at=row[6],
        )

        return ClaimedResearchJob(
            job_id=row[0],
            user_id=row[1],
            topic=row[2],
            scope=row[3],
            research_session_id=row[4],
            lease=lease,
        )

    def renew(
        self,
        lease: ResearchJobLease,
        duration_seconds: int = 120,
    ) -> ResearchJobLease | None:

        self._validate_duration(duration_seconds)

        statement = text("""
            UPDATE dbo.research_jobs
            SET lease_expires_at = DATEADD(
                second,
                :duration_seconds,
                SYSUTCDATETIME()
            )
            OUTPUT INSERTED.lease_expires_at
            WHERE id = :job_id
              AND execution_owner = :owner
              AND lease_version = :version
              AND status = 'claimed'
              AND lease_expires_at > SYSUTCDATETIME()
        """)

        try:

            row = self.db.execute(
                statement,
                {
                    "job_id": lease.job_id,
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

        return ResearchJobLease(
            job_id=lease.job_id,
            owner=lease.owner,
            version=lease.version,
            expires_at=row[0],
        )

    def release(
        self,
        lease: ResearchJobLease,
    ) -> bool:

        # Only unstarted jobs can return to the queue.
        # Increment the version to invalidate the old lease.
        statement = text("""
            UPDATE dbo.research_jobs
            SET status = 'queued',
                execution_owner = NULL,
                lease_expires_at = NULL,
                lease_version = lease_version + 1
            OUTPUT INSERTED.id
            WHERE id = :job_id
              AND execution_owner = :owner
              AND lease_version = :version
              AND status = 'claimed'
              AND research_session_id IS NULL
              AND lease_expires_at > SYSUTCDATETIME()
        """)

        try:

            row = self.db.execute(
                statement,
                {
                    "job_id": lease.job_id,
                    "owner": lease.owner,
                    "version": lease.version,
                },
            ).first()

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        return row is not None

    
    def associate_session(
        self,
        lease: ResearchJobLease,
    ) -> str:

        try:

            # Lock the job row until the transaction commits.
            # This serializes competing association attempts.
            statement = text("""
                SELECT
                    research_session_id,
                    topic,
                    scope
                FROM dbo.research_jobs WITH (
                    UPDLOCK,
                    HOLDLOCK
                )
                WHERE id = :job_id
                  AND execution_owner = :owner
                  AND lease_version = :version
                  AND status = 'claimed'
                  AND lease_expires_at > SYSUTCDATETIME()
            """)

            row = self.db.execute(
                statement,
                {
                    "job_id": lease.job_id,
                    "owner": lease.owner,
                    "version": lease.version,
                },
            ).first()

            if row is None:

                raise ResearchJobLeaseUnavailable(
                    "Cannot associate a research session "
                    "because the job lease is no longer valid."
                )

            existing_session_id = row[0]

            if existing_session_id is not None:

                self.db.commit()

                return str(existing_session_id)

            topic = row[1]
            scope = row[2]

            now = datetime.now(
                timezone.utc
            ).replace(
                tzinfo=None
            )

            session_id = str(uuid4())

            research_session = ResearchSession(
                id=session_id,
                topic=topic,
                scope=scope,
                status="created",
                pause_requested=False,
                created_at=now,
                updated_at=now,
            )

            self.db.add(
                research_session
            )

            # Insert the session within the current transaction.
            # Do not call ResearchSessionRepository.create(),
            # because that method commits independently.
            self.db.flush()

            update_statement = text("""
                UPDATE dbo.research_jobs
                SET research_session_id = :session_id
                WHERE id = :job_id
                  AND execution_owner = :owner
                  AND lease_version = :version
                  AND status = 'claimed'
                  AND research_session_id IS NULL
                  AND lease_expires_at > SYSUTCDATETIME()
            """)

            result = self.db.execute(
                update_statement,
                {
                    "session_id": session_id,
                    "job_id": lease.job_id,
                    "owner": lease.owner,
                    "version": lease.version,
                },
            )

            if result.rowcount != 1:

                raise ResearchJobLeaseUnavailable(
                    "Job ownership changed before "
                    "the research session was associated."
                )

            # The session insert and job association
            # become durable together.
            self.db.commit()

            return session_id

        except Exception:

            self.db.rollback()

            raise

    
    def resume_paused(
        self,
        job_id: str,
        user_id: str,
    ) -> bool:

        try:

            statement = text("""
                SELECT
                    research_session_id
                FROM dbo.research_jobs WITH (
                    UPDLOCK,
                    HOLDLOCK
                )
                WHERE id = :job_id
                  AND user_id = :user_id
                  AND status = 'paused'
                  AND execution_owner IS NULL
                  AND lease_expires_at IS NULL
            """)

            row = self.db.execute(
                statement,
                {
                    "job_id": job_id,
                    "user_id": user_id,
                },
            ).first()

            if row is None:

                self.db.rollback()
                return False

            session_id = row[0]

            if session_id is not None:

                statement = text("""
                    UPDATE dbo.research_sessions
                    SET pause_requested = 0,
                        updated_at = SYSUTCDATETIME()
                    OUTPUT INSERTED.id
                    WHERE id = :session_id
                      AND status <> 'completed'
                      AND (
                          execution_owner IS NULL
                          OR execution_lease_expires_at IS NULL
                          OR execution_lease_expires_at
                              <= SYSUTCDATETIME()
                      )
                """)

                updated = self.db.execute(
                    statement,
                    {
                        "session_id": session_id,
                    },
                ).first()

                if updated is None:

                    self.db.rollback()
                    return False

            statement = text("""
                UPDATE dbo.research_jobs
                SET status = 'queued',
                    submitted_at = SYSUTCDATETIME(),
                    completed_at = NULL,
                    last_error = NULL,
                    lease_version = lease_version + 1
                OUTPUT INSERTED.id
                WHERE id = :job_id
                  AND user_id = :user_id
                  AND status = 'paused'
                  AND execution_owner IS NULL
                  AND lease_expires_at IS NULL
            """)

            updated = self.db.execute(
                statement,
                {
                    "job_id": job_id,
                    "user_id": user_id,
                },
            ).first()

            if updated is None:

                raise RuntimeError(
                    "Could not return paused research job "
                    "to the queue."
                )

            self.db.commit()

            return True

        except Exception:

            self.db.rollback()
            raise


    def request_pause(
        self,
        job_id: str,
        user_id: str,
    ) -> str | None:

        try:

            statement = text("""
                SELECT
                    status,
                    research_session_id
                FROM dbo.research_jobs WITH (
                    UPDLOCK,
                    HOLDLOCK
                )
                WHERE id = :job_id
                  AND user_id = :user_id
            """)

            row = self.db.execute(
                statement,
                {
                    "job_id": job_id,
                    "user_id": user_id,
                },
            ).first()

            if row is None:

                self.db.rollback()
                return None

            status = row[0]
            session_id = row[1]

            if status == "paused":

                self.db.commit()
                return "paused"

            if status == "queued":

                if session_id is not None:

                    statement = text("""
                        UPDATE dbo.research_sessions
                        SET pause_requested = 1,
                            updated_at = SYSUTCDATETIME()
                        OUTPUT INSERTED.id
                        WHERE id = :session_id
                          AND status <> 'completed'
                    """)

                    updated = self.db.execute(
                        statement,
                        {
                            "session_id": session_id,
                        },
                    ).first()

                    if updated is None:

                        self.db.rollback()
                        return None

                statement = text("""
                    UPDATE dbo.research_jobs
                    SET status = 'paused',
                        lease_version = lease_version + 1
                    WHERE id = :job_id
                      AND status = 'queued'
                      AND execution_owner IS NULL
                      AND lease_expires_at IS NULL
                """)

                result = self.db.execute(
                    statement,
                    {
                        "job_id": job_id,
                    },
                )

                if result.rowcount != 1:

                    raise RuntimeError(
                        "Could not pause the queued research job."
                    )

                self.db.commit()
                return "paused"

            if status != "claimed":

                self.db.rollback()
                return None

            if session_id is None:

                self.db.rollback()

                raise RuntimeError(
                    "Research job is being initialised. "
                    "Retry the pause request shortly."
                )

            statement = text("""
                UPDATE dbo.research_sessions
                SET pause_requested = 1,
                    updated_at = SYSUTCDATETIME()
                OUTPUT INSERTED.id
                WHERE id = :session_id
                  AND status <> 'completed'
            """)

            updated = self.db.execute(
                statement,
                {
                    "session_id": session_id,
                },
            ).first()

            if updated is None:

                self.db.rollback()
                return None

            self.db.commit()

            return "pause_requested"

        except Exception:

            self.db.rollback()
            raise


    def pause_claimed(
        self,
        lease: ResearchJobLease,
    ) -> bool:

        statement = text("""
            UPDATE j
            SET status = 'paused',
                execution_owner = NULL,
                lease_expires_at = NULL,
                lease_version = lease_version + 1
            OUTPUT INSERTED.id
            FROM dbo.research_jobs AS j
            INNER JOIN dbo.research_sessions AS s
                ON s.id = j.research_session_id
            WHERE j.id = :job_id
              AND j.execution_owner = :owner
              AND j.lease_version = :version
              AND j.status = 'claimed'
              AND j.lease_expires_at > SYSUTCDATETIME()
              AND s.pause_requested = 1
              AND s.status <> 'completed'
              AND (
                    s.execution_owner IS NULL
                    OR s.execution_lease_expires_at IS NULL
                    OR s.execution_lease_expires_at <= SYSUTCDATETIME()
                )
        """)

        try:

            row = self.db.execute(
                statement,
                {
                    "job_id": lease.job_id,
                    "owner": lease.owner,
                    "version": lease.version,
                },
            ).first()

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        return row is not None
    

    def complete(
        self,
        lease: ResearchJobLease,
    ) -> bool:

        statement = text("""
            UPDATE j
            SET status = 'completed',
                completed_at = SYSUTCDATETIME(),
                execution_owner = NULL,
                lease_expires_at = NULL,
                lease_version = lease_version + 1,
                last_error = NULL
            OUTPUT INSERTED.id
            FROM dbo.research_jobs AS j
            INNER JOIN dbo.research_sessions AS s
                ON s.id = j.research_session_id
            WHERE j.id = :job_id
              AND j.execution_owner = :owner
              AND j.lease_version = :version
              AND j.status = 'claimed'
              AND j.lease_expires_at > SYSUTCDATETIME()
              AND s.status = 'completed'
        """)

        try:

            row = self.db.execute(
                statement,
                {
                    "job_id": lease.job_id,
                    "owner": lease.owner,
                    "version": lease.version,
                },
            ).first()

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        return row is not None


    def reconcile_completed_session(
        self,
        session_id: str,
    ) -> bool:

        if (
            not isinstance(session_id, str)
            or not session_id.strip()
        ):

            raise ValueError(
                "session_id is required"
            )

        session_id = session_id.strip()

        statement = text("""
            UPDATE j
            SET status = 'completed',
                completed_at = SYSUTCDATETIME(),
                execution_owner = NULL,
                lease_expires_at = NULL,
                lease_version = lease_version + 1,
                last_error = NULL
            OUTPUT INSERTED.id
            FROM dbo.research_jobs AS j
            INNER JOIN dbo.research_sessions AS s
                ON s.id = j.research_session_id
            WHERE j.research_session_id = :session_id
              AND j.status = 'claimed'
              AND (
                    j.lease_expires_at IS NULL
                    OR j.lease_expires_at <= SYSUTCDATETIME()
                  )
              AND s.status = 'completed'
        """)

        try:

            row = self.db.execute(
                statement,
                {
                    "session_id": session_id,
                },
            ).first()

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        return row is not None


    def reconcile_abandoned_pauses(
        self,
        limit: int = 100,
    ) -> int:

        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 1000
        ):

            raise ValueError(
                "limit must be an integer from 1 to 1000"
            )

        statement = text("""
            ;WITH abandoned_jobs AS (
                SELECT TOP (:limit)
                    j.id
                FROM dbo.research_jobs AS j WITH (
                    UPDLOCK,
                    READPAST,
                    ROWLOCK
                )
                INNER JOIN dbo.research_sessions AS s
                    ON s.id = j.research_session_id
                WHERE j.status = 'claimed'
                  AND j.lease_expires_at <= SYSUTCDATETIME()
                  AND s.pause_requested = 1
                  AND s.status <> 'completed'
                  AND (
                      s.execution_owner IS NULL
                      OR s.execution_lease_expires_at IS NULL
                      OR s.execution_lease_expires_at
                          <= SYSUTCDATETIME()
                  )
                ORDER BY j.id
            )
            UPDATE j
            SET status = 'paused',
                execution_owner = NULL,
                lease_expires_at = NULL,
                lease_version = lease_version + 1
            OUTPUT INSERTED.id
            FROM dbo.research_jobs AS j
            INNER JOIN abandoned_jobs AS a
                ON a.id = j.id
        """)

        try:

            rows = self.db.execute(
                statement,
                {
                    "limit": limit,
                },
            ).all()

            reconciled_count = len(rows)

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        return reconciled_count

    def reconcile_completed_jobs(
        self,
        limit: int = 100,
    ) -> int:

        if limit < 1:

            raise ValueError(
                "limit must be greater than zero"
            )

        statement = text("""
            ;WITH completed_jobs AS (
                SELECT TOP (:limit)
                    j.id
                FROM dbo.research_jobs AS j WITH (
                    UPDLOCK,
                    READPAST,
                    ROWLOCK
                )
                INNER JOIN dbo.research_sessions AS s
                    ON s.id = j.research_session_id
                WHERE j.status = 'claimed'
                  AND (
                      j.lease_expires_at IS NULL
                      OR j.lease_expires_at <= SYSUTCDATETIME()
                  )
                  AND s.status = 'completed'
                ORDER BY j.id
            )
            UPDATE j
            SET status = 'completed',
                completed_at = SYSUTCDATETIME(),
                execution_owner = NULL,
                lease_expires_at = NULL,
                lease_version = lease_version + 1,
                last_error = NULL
            FROM dbo.research_jobs AS j
            INNER JOIN completed_jobs AS c
                ON c.id = j.id
        """)

        try:

            result = self.db.execute(
                statement,
                {
                    "limit": limit,
                },
            )

            reconciled_count = result.rowcount

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        return reconciled_count
    

    def fail(
        self,
        lease: ResearchJobLease,
        error: str,
    ) -> bool:

        if not isinstance(error, str):

            raise ValueError(
                "error must be a string"
            )

        error = error.strip()

        if not error:

            raise ValueError(
                "error must not be empty"
            )

        statement = text("""
            UPDATE dbo.research_jobs
            SET status = 'failed',
                execution_owner = NULL,
                lease_expires_at = NULL,
                lease_version = lease_version + 1,
                last_error = :error
            OUTPUT INSERTED.id
            WHERE id = :job_id
            AND execution_owner = :owner
            AND lease_version = :version
            AND status = 'claimed'
            AND lease_expires_at > SYSUTCDATETIME()
        """)

        try:

            row = self.db.execute(
                statement,
                {
                    "job_id": lease.job_id,
                    "owner": lease.owner,
                    "version": lease.version,
                    "error": error,
                },
            ).first()

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        return row is not None

    
    def retry_failed(
        self,
        job_id: str,
        user_id: str,
    ) -> bool:

        if (
            not isinstance(job_id, str)
            or not job_id.strip()
        ):

            raise ValueError(
                "job_id is required"
            )

        if (
            not isinstance(user_id, str)
            or not user_id.strip()
        ):

            raise ValueError(
                "user_id is required"
            )

        job_id = job_id.strip()
        user_id = user_id.strip()

        statement = text("""
            UPDATE j
            SET status = 'queued',
                submitted_at = SYSUTCDATETIME(),
                started_at = NULL,
                completed_at = NULL,
                last_error = NULL
            OUTPUT INSERTED.id
            FROM dbo.research_jobs AS j
            INNER JOIN dbo.research_sessions AS s
                ON s.id = j.research_session_id
            WHERE j.id = :job_id
              AND j.user_id = :user_id
              AND j.status = 'failed'
              AND j.research_session_id IS NOT NULL
              AND j.execution_owner IS NULL
              AND j.lease_expires_at IS NULL
              AND s.pause_requested = 0
              AND s.status IN (
                  'created',
                  'planning',
                  'planned',
                  'researching',
                  'researched',
                  'reviewing',
                  'reviewed',
                  'reporting',
                  'completed'
              )
              AND (
                s.execution_owner IS NULL
                OR s.execution_lease_expires_at IS NULL
                OR s.execution_lease_expires_at <= SYSUTCDATETIME()
            )
        """)

        try:

            row = self.db.execute(
                statement,
                {
                    "job_id": job_id,
                    "user_id": user_id,
                },
            ).first()

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise

        return row is not None
