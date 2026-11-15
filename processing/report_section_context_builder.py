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

from domain.report_plan import (
    PlannedReportSection,
)

from domain.review import (
    PersistedQuestionReview,
)


class ReportSectionContextBuilder:

    def build(
        self,
        reviews: list[PersistedQuestionReview],
        section: PlannedReportSection,
    ) -> str:

        permitted_claim_ids = set(
            section.reviewed_claim_ids
        )

        lines = []

        included_claim_ids = set()

        for review in reviews:

            selected_claims = [
                claim
                for claim in review.reviewed_claims
                if claim.id in permitted_claim_ids
            ]

            if not selected_claims:

                continue

            lines.append(
                f"RESEARCH QUESTION: {review.question}"
            )

            lines.append(
                f"RESEARCH CATEGORY: {review.category}"
            )

            lines.append(
                "OVERALL REVIEW CONFIDENCE: "
                f"{review.overall_confidence}"
            )

            lines.append(
                "SUFFICIENT EVIDENCE: "
                f"{review.sufficient_evidence}"
            )

            lines.append("")

            for claim in selected_claims:

                included_claim_ids.add(
                    claim.id
                )

                lines.append(
                    f"REVIEWED CLAIM ID: {claim.id}"
                )

                lines.append(
                    f"CLAIM: {claim.claim}"
                )

                lines.append(
                    f"CONFIDENCE: {claim.confidence}"
                )

                supporting_ids = ", ".join(
                    str(finding_id)
                    for finding_id
                    in claim.supporting_finding_ids
                )

                contradicting_ids = ", ".join(
                    str(finding_id)
                    for finding_id
                    in claim.contradicting_finding_ids
                )

                lines.append(
                    "SUPPORTING FINDING IDS: "
                    f"{supporting_ids or 'None'}"
                )

                lines.append(
                    "CONTRADICTING FINDING IDS: "
                    f"{contradicting_ids or 'None'}"
                )

                lines.append("")

            lines.append(
                "-" * 60
            )

            lines.append("")

        missing_claim_ids = (
            permitted_claim_ids
            - included_claim_ids
        )

        if missing_claim_ids:

            missing_text = ", ".join(
                str(claim_id)
                for claim_id in sorted(
                    missing_claim_ids
                )
            )

            raise ValueError(
                "Section references reviewed claims "
                "not found in the supplied reviews: "
                f"{missing_text}"
            )

        return "\n".join(
            lines
        )
