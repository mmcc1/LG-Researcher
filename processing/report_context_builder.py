from domain.review import (
    PersistedQuestionReview,
    PersistedReviewedClaim,
)


class ReportContextBuilder:

    def build(
        self,
        reviews: list[
            PersistedQuestionReview
        ],
    ) -> str:

        parts = []

        for review in reviews:

            parts.append(
                self._build_review(
                    review
                )
            )

        return (
            "\n\n"
            "================================"
            "\n\n"
        ).join(parts)


    def _build_review(
        self,
        review: PersistedQuestionReview,
    ) -> str:

        parts = [
            (
                f"QUESTION ID: "
                f"{review.research_question_id}"
            ),
            (
                f"CATEGORY: "
                f"{review.category}"
            ),
            (
                "QUESTION:\n"
                f"{review.question}"
            ),
            (
                "REVIEWED ANSWER:\n"
                f"{review.answer}"
            ),
            (
                "OVERALL CONFIDENCE: "
                f"{review.overall_confidence}"
            ),
            (
                "SUFFICIENT EVIDENCE: "
                f"{review.sufficient_evidence}"
            ),
        ]

        #
        # Reviewed claims.
        #

        if review.reviewed_claims:

            claim_parts = []

            for claim in (
                review.reviewed_claims
            ):

                claim_parts.append(
                    self._build_claim(
                        claim
                    )
                )

            parts.append(
                "REVIEWED CLAIMS:\n\n"
                + "\n\n".join(
                    claim_parts
                )
            )

        else:

            parts.append(
                "REVIEWED CLAIMS:\n"
                "None"
            )

        #
        # Contradictions identified during
        # evidence review.
        #

        if review.contradictions:

            contradiction_text = "\n".join(
                f"- {contradiction}"
                for contradiction
                in review.contradictions
            )

            parts.append(
                "CONTRADICTIONS:\n"
                + contradiction_text
            )

        else:

            parts.append(
                "CONTRADICTIONS:\n"
                "None"
            )

        #
        # Evidence gaps identified during
        # evidence review.
        #

        if review.evidence_gaps:

            gap_text = "\n".join(
                f"- {gap}"
                for gap
                in review.evidence_gaps
            )

            parts.append(
                "EVIDENCE GAPS:\n"
                + gap_text
            )

        else:

            parts.append(
                "EVIDENCE GAPS:\n"
                "None"
            )

        return "\n\n".join(
            parts
        )


    def _build_claim(
        self,
        claim: PersistedReviewedClaim,
    ) -> str:

        supporting_ids = (
            ", ".join(
                str(finding_id)
                for finding_id
                in claim.supporting_finding_ids
            )
        )

        if not supporting_ids:
            supporting_ids = "None"

        contradicting_ids = (
            ", ".join(
                str(finding_id)
                for finding_id
                in claim.contradicting_finding_ids
            )
        )

        if not contradicting_ids:
            contradicting_ids = "None"

        return (
            f"REVIEWED CLAIM ID: {claim.id}\n"
            f"CLAIM:\n{claim.claim}\n"
            f"CONFIDENCE: {claim.confidence}\n"
            f"SUPPORTING FINDING IDS: "
            f"{supporting_ids}\n"
            f"CONTRADICTING FINDING IDS: "
            f"{contradicting_ids}"
        )