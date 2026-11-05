from agents.review_agent import (
    ReviewAgent,
)

from domain.review import (
    ResearchQuestionReview,
    ReviewedClaim,
)


print()
print(
    "REVIEW PROVENANCE VALIDATION TEST"
)
print(
    "================================="
)


valid_finding_ids = {
    100,
    101,
    102,
}


#
# -------------------------------------------------
# Test 1:
# Completely valid provenance.
# -------------------------------------------------
#

valid_review = ResearchQuestionReview(
    answer="Test answer.",
    reviewed_claims=[
        ReviewedClaim(
            claim="Test claim.",
            supporting_finding_ids=[
                100,
                101,
            ],
            contradicting_finding_ids=[
                102,
            ],
            confidence="medium",
        ),
    ],
    contradictions=[],
    evidence_gaps=[],
    overall_confidence="medium",
    sufficient_evidence=True,
)


invalid_ids = (
    ReviewAgent
    ._get_invalid_finding_ids(
        review=valid_review,
        valid_finding_ids=(
            valid_finding_ids
        ),
    )
)


overlapping_ids = (
    ReviewAgent
    ._get_overlapping_finding_ids(
        review=valid_review,
    )
)


assert invalid_ids == set()

assert overlapping_ids == set()


print(
    "Valid provenance detection: PASSED"
)


#
# -------------------------------------------------
# Test 2:
# Hallucinated finding ID.
#
# This reproduces the class of failure seen in the
# real Q100 review, where Qwen returned finding 393
# even though it was outside the valid namespace.
# -------------------------------------------------
#

invalid_review = ResearchQuestionReview(
    answer="Test answer.",
    reviewed_claims=[
        ReviewedClaim(
            claim="Test claim.",
            supporting_finding_ids=[
                100,
                393,
            ],
            contradicting_finding_ids=[
                102,
            ],
            confidence="medium",
        ),
    ],
    contradictions=[],
    evidence_gaps=[],
    overall_confidence="medium",
    sufficient_evidence=True,
)


invalid_ids = (
    ReviewAgent
    ._get_invalid_finding_ids(
        review=invalid_review,
        valid_finding_ids=(
            valid_finding_ids
        ),
    )
)


assert invalid_ids == {
    393,
}


print(
    "Invalid provenance detection: PASSED"
)


#
# -------------------------------------------------
# Test 3:
# Same finding used as both supporting and
# contradicting the same reviewed claim.
# -------------------------------------------------
#

overlapping_review = ResearchQuestionReview(
    answer="Test answer.",
    reviewed_claims=[
        ReviewedClaim(
            claim="Test claim.",
            supporting_finding_ids=[
                100,
                101,
            ],
            contradicting_finding_ids=[
                101,
                102,
            ],
            confidence="medium",
        ),
    ],
    contradictions=[],
    evidence_gaps=[],
    overall_confidence="medium",
    sufficient_evidence=True,
)


overlapping_ids = (
    ReviewAgent
    ._get_overlapping_finding_ids(
        review=overlapping_review,
    )
)


assert overlapping_ids == {
    101,
}


print(
    "Overlapping provenance detection: PASSED"
)


#
# -------------------------------------------------
# Test 4:
# Multiple claims containing multiple invalid IDs.
#
# The result should be a deduplicated set of all
# invalid provenance references.
# -------------------------------------------------
#

multiple_invalid_review = (
    ResearchQuestionReview(
        answer="Test answer.",
        reviewed_claims=[
            ReviewedClaim(
                claim="First claim.",
                supporting_finding_ids=[
                    100,
                    393,
                ],
                contradicting_finding_ids=[],
                confidence="medium",
            ),
            ReviewedClaim(
                claim="Second claim.",
                supporting_finding_ids=[
                    999,
                ],
                contradicting_finding_ids=[
                    393,
                    102,
                ],
                confidence="low",
            ),
        ],
        contradictions=[],
        evidence_gaps=[],
        overall_confidence="medium",
        sufficient_evidence=True,
    )
)


invalid_ids = (
    ReviewAgent
    ._get_invalid_finding_ids(
        review=multiple_invalid_review,
        valid_finding_ids=(
            valid_finding_ids
        ),
    )
)


assert invalid_ids == {
    393,
    999,
}


print(
    "Multiple invalid provenance detection: "
    "PASSED"
)


print()
print(
    "================================="
)
print("PASS")
print(
    "================================="
)

print(
    "Review provenance validation "
    "behaves as expected."
)