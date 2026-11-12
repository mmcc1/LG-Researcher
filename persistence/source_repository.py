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
from persistence.models import WebSearchResult
from sqlalchemy.orm import Session

from domain.source import SourceDocument
from persistence.models import Source

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)

from persistence.models import ResearchQuestion


class SourceRepository:

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def exists_for_url(
        self,
        session_id: str,
        url: str,
    ) -> bool:

        source = (
            self.db.query(Source)
            .filter(
                Source.research_session_id
                == session_id,

                Source.requested_url
                == url,
            )
            .first()
        )

        return source is not None

    
    def save(
        self,
        session_id: str,
        question_id: int,
        document: SourceDocument,
        lease: ExecutionLease,
    ) -> Source:

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

            existing = (
                self.db.query(Source)
                .filter(
                    Source.research_session_id
                    == session_id,
                    Source.requested_url
                    == document.requested_url,
                )
                .order_by(
                    Source.id
                )
                .first()
            )

            if existing is not None:

                self.db.commit()

                return existing

            source = Source(
                research_session_id=session_id,
                research_question_id=question_id,
                requested_url=document.requested_url,
                final_url=document.final_url,
                title=document.title,
                content_type=document.content_type,
                status_code=document.status_code,
                content_hash=document.content_hash,
                raw_content=document.raw_content,
                extracted_text=document.extracted_text,
                created_at=datetime.now(
                    timezone.utc
                ),
            )

            self.db.add(
                source
            )

            self.db.flush()

            self.db.commit()

            return source

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

    def get_for_question(
            self,
            question_id: int,
            ) -> list[Source]:

        return (
            self.db.query(Source)
            .filter(
                Source.research_question_id
                == question_id
            )
            .order_by(
                Source.id
            )
            .all()
        )


    def get_by_id(
            self,
            source_id: int,
        ) -> Source | None:

        return self.db.get(
            Source,
            source_id,
        )

    def get_by_ids(
        self,
        source_ids: set[int],
    ) -> list[Source]:

        if not source_ids:
            return []

        return (
            self.db.query(Source)
            .filter(
                Source.id.in_(source_ids)
            )
            .order_by(Source.id)
            .all()
        )