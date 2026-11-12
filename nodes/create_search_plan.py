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

from agents.search_planner import (
    SearchPlanner,
)

from graph.state import (
    ResearchState,
)

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.finding_repository import (
    FindingRepository,
)

from processing.counter_evidence_context_builder import (
    CounterEvidenceContextBuilder,
)


class CreateSearchPlanNode:

    def __init__(
        self,
        search_planner: SearchPlanner,
        session_factory,
        counter_evidence_context_builder:
            CounterEvidenceContextBuilder | None = None,
    ):
        self.search_planner = search_planner
        self.session_factory = session_factory

        self.counter_evidence_context_builder = (
            counter_evidence_context_builder
            or CounterEvidenceContextBuilder()
        )

    def __call__(
        self,
        state: ResearchState,
    ) -> dict:

        question = state[
            "current_question"
        ]

        if question is None:
            raise ValueError(
                "No research question selected."
            )

        attempt_id = state.get(
            "current_search_attempt_id"
        )

        if attempt_id is None:
            raise ValueError(
                "No active search attempt "
                "is associated with the "
                "current research question."
            )

        existing_evidence_context = None

        with self.session_factory() as db:

            attempt_repository = (
                SearchAttemptRepository(db)
            )

            research_session_repository = (
                ResearchSessionRepository(db)
            )

            attempt = (
                attempt_repository.get(
                    attempt_id
                )
            )

            if attempt is None:
                raise ValueError(
                    "Search attempt not found: "
                    f"{attempt_id}"
                )

            #
            # Protect against a stale or incorrectly
            # correlated graph-state attempt ID.
            #

            if (
                attempt.research_session_id
                != state["session_id"]
            ):
                raise ValueError(
                    "Search attempt does not belong "
                    "to the current research session."
                )

            if (
                attempt.research_question_id
                != state["current_question_id"]
            ):
                raise ValueError(
                    "Search attempt does not belong "
                    "to the current research question."
                )

            if attempt.status != "running":
                raise ValueError(
                    "Search planning requires a "
                    "running search attempt."
                )

            #
            # Load the authoritative durable research
            # session from SQL.
            #
            # Scope is deliberately not taken from
            # LangGraph state because SQL owns the
            # durable research definition.
            #

            research_session = (
                research_session_repository.get(
                    state["session_id"]
                )
            )

            if research_session is None:
                raise ValueError(
                    "Research session not found: "
                    f"{state['session_id']}"
                )

            #
            # Protect against stale graph-state topic
            # data as well. The persisted session is
            # authoritative for both topic and scope.
            #

            topic = research_session.topic
            scope = research_session.scope

            #
            # Copy durable attempt values while the
            # SQL session is open.
            #

            purpose = attempt.purpose

            instructions = (
                attempt.instructions
            )

            #
            # Counter-evidence planning needs to know
            # what the existing research actually
            # claims.
            #
            # Initial and deeper-research searches do
            # not receive this context.
            #

            if purpose == "counter_evidence":

                finding_repository = (
                    FindingRepository(db)
                )

                findings = (
                    finding_repository
                    .get_for_question(
                        attempt.research_question_id
                    )
                )

                existing_evidence_context = (
                    self
                    .counter_evidence_context_builder
                    .build(
                        findings
                    )
                )

        print(
            "Creating search plan for "
            f"attempt {attempt_id} "
            f"({purpose})."
        )

        if scope:

            print(
                "Search plan includes persistent "
                "research scope."
            )

        if instructions:

            print(
                "Search attempt includes "
                "additional research instructions."
            )

        if (
            purpose == "counter_evidence"
            and existing_evidence_context
        ):

            print(
                "Counter-evidence search plan "
                "includes existing research claims."
            )

        plan = (
            self.search_planner.create_plan(
                topic=topic,
                question=question,
                scope=scope,
                purpose=purpose,
                instructions=instructions,
                existing_evidence_context=(
                    existing_evidence_context
                ),
            )
        )

        return {
            "search_plan": plan
        }