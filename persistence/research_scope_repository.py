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

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy.orm import (
    Session,
)

from domain.research_scope import (
    ResearchScopeDefinition,
)

from persistence.models import (
    ResearchScopeDefinitionEntity,
    ResearchSession,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)


class ResearchScopeRepository:

    def __init__(
        self,
        db: Session,
    ):

        self.db = db

    def get(
        self,
        session_id: str,
    ) -> ResearchScopeDefinition | None:

        entity = self.db.get(
            ResearchScopeDefinitionEntity,
            session_id,
        )

        if entity is None:
            return None

        if entity.schema_version != 1:

            raise ValueError(
                "Unsupported research scope "
                "definition schema version: "
                f"{entity.schema_version}"
            )

        definition_data = json.loads(
            entity.definition_json
        )

        return ResearchScopeDefinition.model_validate(
            definition_data
        )

    def save(
        self,
        session_id: str,
        definition: ResearchScopeDefinition,
        lease: ExecutionLease,
    ) -> ResearchScopeDefinition:

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

            research_session = self.db.get(
                ResearchSession,
                session_id,
                populate_existing=True,
            )

            if research_session is None:

                raise ValueError(
                    "Research session not found: "
                    f"{session_id}"
                )

            existing_definition = self.get(
                session_id
            )

            if existing_definition is not None:

                self.db.commit()

                return existing_definition

            if research_session.status != "planning":

                raise ValueError(
                    "Research session is not ready "
                    "for scope definition persistence."
                )

            definition_json = (
                definition.model_dump_json()
            )

            entity = ResearchScopeDefinitionEntity(
                research_session_id=session_id,
                definition_json=definition_json,
                schema_version=1,
                created_at=datetime.now(
                    timezone.utc
                ),
            )

            self.db.add(
                entity
            )

            self.db.commit()

            return definition

        except Exception:

            self.db.rollback()

            raise