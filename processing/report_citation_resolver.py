
#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron
#
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

from sqlalchemy.orm import (
    Session,
)

from domain.report_citation import (
    CitationSource,
    ClaimSourceProvenance,
    ReportCitationProvenance,
)

from persistence.models import (
    Finding,
    QuestionReview,
    ResearchQuestion,
    ReviewedClaimEntity,
    ReviewedClaimSupport,
    ReviewedClaimContradiction,
    Source,
)


class ReportCitationResolver:

    def __init__(
        self,
        db: Session,
    ):

        self.db = db

    def resolve(
        self,
        session_id: str,
        reviewed_claim_ids: list[int],
    ) -> ReportCitationProvenance:

        ordered_claim_ids = list(
            dict.fromkeys(
                reviewed_claim_ids
            )
        )

        if not ordered_claim_ids:

            return ReportCitationProvenance(
                research_session_id=session_id,
                claims=[],
            )

        claim_rows = (
            self.db.query(
                ReviewedClaimEntity.id
            )
            .join(
                QuestionReview,
                ReviewedClaimEntity.question_review_id
                == QuestionReview.id,
            )
            .join(
                ResearchQuestion,
                QuestionReview.research_question_id
                == ResearchQuestion.id,
            )
            .filter(
                ResearchQuestion.research_session_id
                == session_id,
                ReviewedClaimEntity.id.in_(
                    ordered_claim_ids
                ),
            )
            .all()
        )

        valid_claim_ids = {
            row[0]
            for row in claim_rows
        }

        invalid_claim_ids = (
            set(ordered_claim_ids)
            - valid_claim_ids
        )

        if invalid_claim_ids:

            invalid_text = ", ".join(
                str(claim_id)
                for claim_id in sorted(
                    invalid_claim_ids
                )
            )

            raise ValueError(
                "Reviewed claims do not belong "
                "to the requested research session: "
                f"{invalid_text}"
            )

        supporting_sources = (
            self._load_sources(
                session_id=session_id,
                reviewed_claim_ids=ordered_claim_ids,
                association_model=ReviewedClaimSupport,
            )
        )

        contradicting_sources = (
            self._load_sources(
                session_id=session_id,
                reviewed_claim_ids=ordered_claim_ids,
                association_model=ReviewedClaimContradiction,
            )
        )

        claims = []

        for claim_id in ordered_claim_ids:

            claim_supporting_sources = (
                supporting_sources.get(
                    claim_id,
                    [],
                )
            )

            claim_contradicting_sources = (
                contradicting_sources.get(
                    claim_id,
                    [],
                )
            )

            if not claim_supporting_sources:

                raise ValueError(
                    "Reviewed claim has no resolvable "
                    "supporting source: "
                    f"{claim_id}"
                )

            claims.append(
                ClaimSourceProvenance(
                    reviewed_claim_id=claim_id,
                    supporting_sources=(
                        claim_supporting_sources
                    ),
                    contradicting_sources=(
                        claim_contradicting_sources
                    ),
                )
            )

        return ReportCitationProvenance(
            research_session_id=session_id,
            claims=claims,
        )

    def _load_sources(
        self,
        session_id: str,
        reviewed_claim_ids: list[int],
        association_model,
    ) -> dict[int, list[CitationSource]]:

        rows = (
            self.db.query(
                association_model.reviewed_claim_id,
                association_model.finding_id,
                ResearchQuestion.id,
                Finding,
                Source,
            )
            .select_from(
                association_model
            )
            .join(
                ReviewedClaimEntity,
                association_model.reviewed_claim_id
                == ReviewedClaimEntity.id,
            )
            .join(
                QuestionReview,
                ReviewedClaimEntity.question_review_id
                == QuestionReview.id,
            )
            .join(
                ResearchQuestion,
                QuestionReview.research_question_id
                == ResearchQuestion.id,
            )
            .outerjoin(
                Finding,
                association_model.finding_id
                == Finding.id,
            )
            .outerjoin(
                Source,
                Finding.source_id
                == Source.id,
            )
            .filter(
                association_model.reviewed_claim_id.in_(
                    reviewed_claim_ids
                ),
                ResearchQuestion.research_session_id
                == session_id,
            )
            .order_by(
                association_model.reviewed_claim_id,
                Source.id,
                association_model.finding_id,
            )
            .all()
        )

        sources_by_claim = {}

        seen_source_ids = {}

        for (
            claim_id,
            finding_id,
            question_id,
            finding,
            source,
        ) in rows:

            if finding is None:

                raise ValueError(
                    f"Reviewed claim {claim_id} references "
                    f"a missing finding: {finding_id}"
                )

            if finding.research_question_id != question_id:

                raise ValueError(
                    f"Reviewed claim {claim_id} references "
                    f"finding {finding_id} belonging to "
                    "another research question."
                )

            if source is None:

                raise ValueError(
                    f"Finding {finding_id} references "
                    f"a missing source: {finding.source_id}"
                )

            if (
                source.research_session_id != session_id
                or source.research_question_id != question_id
            ):

                raise ValueError(
                    f"Finding {finding_id} references "
                    f"source {source.id} outside the "
                    "current research question."
                )

            source_text = source.extracted_text

            if not source_text or not source_text.strip():

                raise ValueError(
                    f"Reviewed claim {claim_id} references "
                    f"finding {finding_id} supported by "
                    "a source containing no usable "
                    f"research text: {source.id}"
                )

            if claim_id not in sources_by_claim:

                sources_by_claim[
                    claim_id
                ] = []

                seen_source_ids[
                    claim_id
                ] = set()

            if source.id in seen_source_ids[
                claim_id
            ]:

                continue

            seen_source_ids[
                claim_id
            ].add(
                source.id
            )

            sources_by_claim[
                claim_id
            ].append(
                CitationSource(
                    source_id=source.id,
                    title=source.title or "",
                    requested_url=(
                        source.requested_url
                    ),
                    final_url=source.final_url,
                    content_hash=(
                        source.content_hash
                    ),
                )
            )

        return sources_by_claim