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

from domain.finding import SourceAnalysis
from persistence.models import (
    Finding,
    SourceSummary,
)
from sqlalchemy import text

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)

class FindingRepository:

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    
    def save_analysis(
        self,
        source_id: int,
        question_id: int,
        analysis: SourceAnalysis,
        lease: ExecutionLease,
    ) -> None:

        try:

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            ownership = self.db.execute(
                text("""
                    SELECT s.id
                    FROM dbo.sources AS s
                    INNER JOIN dbo.research_questions AS q
                        ON q.id = :question_id
                    WHERE s.id = :source_id
                      AND s.research_question_id = q.id
                      AND s.research_session_id = :session_id
                      AND q.research_session_id = :session_id
                """),
                {
                    "source_id": source_id,
                    "question_id": question_id,
                    "session_id": lease.session_id,
                },
            ).first()

            if ownership is None:

                raise ValueError(
                    "Source and research question do not "
                    "belong to the execution session."
                )

            existing_analysis = (
                self.db.query(SourceSummary)
                .filter(
                    SourceSummary.source_id
                    == source_id,
                    SourceSummary.research_question_id
                    == question_id,
                )
                .first()
            )

            if existing_analysis is not None:

                self.db.commit()

                return

            now = datetime.now(timezone.utc)

            summary = SourceSummary(
                source_id=source_id,
                research_question_id=question_id,
                summary=analysis.summary,
                created_at=now,
            )

            self.db.add(
                summary
            )

            for extracted in analysis.findings:

                finding = Finding(
                    source_id=source_id,
                    research_question_id=question_id,
                    claim=extracted.claim,
                    evidence=extracted.evidence,
                    relevance=extracted.relevance,
                    confidence=extracted.confidence,
                    created_at=now,
                )

                self.db.add(
                    finding
                )

            self.db.commit()

        except Exception:

            self.db.rollback()
            raise


        
    def analysis_exists(
        self,
        source_id: int,
        question_id: int,
    ) -> bool:

        return (
            self.db.query(SourceSummary)
            .filter(
                SourceSummary.source_id
                == source_id,
                SourceSummary.research_question_id
                == question_id,
            )
            .first()
            is not None
        )

    def get_for_question(
        self,
        question_id: int,
    ) -> list[Finding]:

        return (
            self.db.query(Finding)
            .filter(
                Finding.research_question_id
                == question_id
            )
            .order_by(
                Finding.source_id,
                Finding.id,
            )
            .all()
        )