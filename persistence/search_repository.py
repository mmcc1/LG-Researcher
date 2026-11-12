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

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from domain.search import SearchResult
from persistence.models import WebSearchResult

from sqlalchemy import text

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)

from persistence.models import (
    ResearchQuestion,
    SearchAttempt,
)


class SearchRepository:

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def add_results(
        self,
        session_id: str,
        question_id: int,
        results: list[SearchResult],
        attempt_id: int | None = None,
    ) -> None:

        now = datetime.now(
            timezone.utc
        )

        for result in results:

            entity = WebSearchResult(
                research_session_id=session_id,
                research_question_id=question_id,
                search_attempt_id=attempt_id,
                query=result.query,
                provider=result.provider,
                rank=result.rank,
                url=result.url,
                title=result.title,
                snippet=result.snippet,
                created_at=now,
            )

            self.db.add(
                entity
            )

    def save_results(
        self,
        session_id: str,
        question_id: int,
        results: list[SearchResult],
        attempt_id: int | None = None,
    ) -> None:

        try:

            self.add_results(
                session_id=session_id,
                question_id=question_id,
                results=results,
                attempt_id=attempt_id,
            )

            self.db.commit()

        except Exception:

            self.db.rollback()

            raise

    def get_results_for_question(
        self,
        question_id: int,
    ) -> list[WebSearchResult]:

        return (
            self.db.query(WebSearchResult)
            .filter(
                WebSearchResult.research_question_id
                == question_id
            )
            .order_by(
                WebSearchResult.id
            )
            .all()
        )

    def get_results_for_attempt(
        self,
        attempt_id: int,
    ) -> list[WebSearchResult]:

        return (
            self.db.query(WebSearchResult)
            .filter(
                WebSearchResult.search_attempt_id
                == attempt_id
            )
            .order_by(
                WebSearchResult.id
            )
            .all()
        )

    def has_results_for_question(
        self,
        question_id: int,
    ) -> bool:

        return (
            self.db.query(WebSearchResult)
            .filter(
                WebSearchResult.research_question_id
                == question_id
            )
            .first()
            is not None
        )

    
    def save_attempt_results(
        self,
        session_id: str,
        question_id: int,
        attempt_id: int,
        results: list[SearchResult],
        lease: ExecutionLease,
    ) -> None:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            question = self.db.get(
                ResearchQuestion,
                question_id,
            )

            if (
                question is None
                or question.research_session_id
                != session_id
            ):

                raise ValueError(
                    "Research question does not belong "
                    "to the execution session."
                )

            attempt = self.db.execute(
                text(
                    """
                    SELECT
                        id,
                        research_session_id,
                        research_question_id,
                        status
                    FROM dbo.search_attempts
                    WITH (UPDLOCK, HOLDLOCK)
                    WHERE id = :attempt_id
                    """
                ),
                {
                    "attempt_id": attempt_id,
                },
            ).first()

            if attempt is None:

                raise ValueError(
                    "Search attempt not found."
                )

            if (
                attempt.research_session_id
                != session_id
                or attempt.research_question_id
                != question_id
            ):

                raise ValueError(
                    "Search attempt does not belong "
                    "to the specified research question "
                    "and session."
                )

            existing_results = (
                self.get_results_for_attempt(
                    attempt_id
                )
            )

            def result_signature(result):

                return (
                    result.query,
                    result.provider,
                    result.rank,
                    result.url,
                    result.title,
                    result.snippet,
                )

            requested_signatures = [
                result_signature(result)
                for result in results
            ]

            existing_signatures = [
                result_signature(result)
                for result in existing_results
            ]

            if attempt.status == "completed":

                if (
                    existing_signatures
                    != requested_signatures
                ):

                    raise ValueError(
                        "Completed search attempt has "
                        "different persisted results."
                    )

                self.db.commit()

                return

            if attempt.status != "running":

                raise ValueError(
                    "Only a running search attempt "
                    "can save completed results."
                )

            if existing_results:

                raise ValueError(
                    "Search attempt already contains "
                    "results but is not completed."
                )

            self.add_results(
                session_id=session_id,
                question_id=question_id,
                results=results,
                attempt_id=attempt_id,
            )

            self.db.flush()

            now = datetime.now(
                timezone.utc
            )

            update_result = self.db.execute(
                text(
                    """
                    UPDATE dbo.search_attempts
                    SET
                        status = 'completed',
                        updated_at = :now,
                        completed_at = :now
                    WHERE id = :attempt_id
                    AND status = 'running'
                    """
                ),
                {
                    "attempt_id": attempt_id,
                    "now": now,
                },
            )

            if update_result.rowcount != 1:

                raise RuntimeError(
                    "Search attempt completion failed. "
                    "The attempt is no longer running."
                )

            self.db.commit()

        except Exception:

            self.db.rollback()

            raise
