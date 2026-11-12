from agents.review_agent import (
    ReviewAgent,
)

from domain.review import (
    ResearchQuestionReview,
    ReviewedClaim,
)


print()
print(
    "REVIEW PROVENANCE REPAIR TEST"
)
print(
    "============================="
)


#
# -------------------------------------------------
# Test infrastructure.
#
# ReviewAgent expects:
#
#     model.with_structured_output(...)
#
# followed by:
#
#     structured_model.invoke(messages)
#
# This fake implements only that boundary.
# -------------------------------------------------
#

class FakeStructuredModel:

    def __init__(
        self,
        responses,
    ):
        self.responses = list(
            responses
        )

        self.invoke_count = 0

        self.messages_received = []

    def invoke(
        self,
        messages,
    ):
        self.invoke_count += 1

        self.messages_received.append(
            messages
        )

        if not self.responses:
            raise ValueError(
                "Fake model has no remaining "
                "responses."
            )

        return self.responses.pop(0)


class FakeChatModel:

    def __init__(
        self,
        responses,
    ):
        self.structured_model = (
            FakeStructuredModel(
                responses=responses,
            )
        )

    def with_structured_output(
        self,
        schema,
    ):
        return self.structured_model


#
# -------------------------------------------------
# Shared test data.
# -------------------------------------------------
#

valid_finding_ids = {
    100,
    101,
    102,
}


invalid_review = ResearchQuestionReview(
    answer=(
        "Initial review containing invalid "
        "provenance."
    ),
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


valid_repaired_review = (
    ResearchQuestionReview(
        answer=(
            "Corrected evidence-based answer."
        ),
        reviewed_claims=[
            ReviewedClaim(
                claim="Corrected test claim.",
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
)


#
# -------------------------------------------------
# Test 1:
#
# Invalid first response.
# Valid second response.
#
# The ReviewAgent should:
#
#   1. detect 393
#   2. invoke the model again
#   3. validate the repaired response
#   4. return the repaired response
# -------------------------------------------------
#

print()
print(
    "TEST 1 - SUCCESSFUL REPAIR"
)
print(
    "--------------------------"
)


fake_model = FakeChatModel(
    responses=[
        invalid_review,
        valid_repaired_review,
    ]
)


review_agent = ReviewAgent(
    model=fake_model,
)


result = review_agent.review(
    research_question=(
        "Test research question?"
    ),
    findings_text=(
        "Finding ID 100: First finding.\n"
        "Finding ID 101: Second finding.\n"
        "Finding ID 102: Third finding."
    ),
    valid_finding_ids=(
        valid_finding_ids
    ),
)


assert (
    fake_model
    .structured_model
    .invoke_count
    == 2
)


assert (
    result
    == valid_repaired_review
)


returned_invalid_ids = (
    ReviewAgent
    ._get_invalid_finding_ids(
        review=result,
        valid_finding_ids=(
            valid_finding_ids
        ),
    )
)


assert (
    returned_invalid_ids
    == set()
)


returned_overlapping_ids = (
    ReviewAgent
    ._get_overlapping_finding_ids(
        review=result,
    )
)


assert (
    returned_overlapping_ids
    == set()
)


#
# Verify that the repair invocation was explicitly
# informed about the invalid provenance ID.
#

repair_messages = (
    fake_model
    .structured_model
    .messages_received[1]
)


repair_message_text = "\n".join(
    message.content
    for message in repair_messages
)


assert (
    "393"
    in repair_message_text
)


assert (
    "100, 101, 102"
    in repair_message_text
)


print(
    "Successful repair lifecycle: PASSED"
)


#
# -------------------------------------------------
# Test 2:
#
# Invalid first response.
# Invalid repair response.
#
# The ReviewAgent must fail closed rather than
# returning invalid provenance.
# -------------------------------------------------
#

print()
print(
    "TEST 2 - FAILED REPAIR"
)
print(
    "----------------------"
)


second_invalid_review = (
    ResearchQuestionReview(
        answer=(
            "Second invalid review."
        ),
        reviewed_claims=[
            ReviewedClaim(
                claim=(
                    "Still-invalid test claim."
                ),
                supporting_finding_ids=[
                    100,
                    999,
                ],
                contradicting_finding_ids=[],
                confidence="low",
            ),
        ],
        contradictions=[],
        evidence_gaps=[],
        overall_confidence="low",
        sufficient_evidence=False,
    )
)


fake_model = FakeChatModel(
    responses=[
        invalid_review,
        second_invalid_review,
    ]
)


review_agent = ReviewAgent(
    model=fake_model,
)


try:

    review_agent.review(
        research_question=(
            "Test research question?"
        ),
        findings_text=(
            "Finding ID 100: First finding.\n"
            "Finding ID 101: Second finding.\n"
            "Finding ID 102: Third finding."
        ),
        valid_finding_ids=(
            valid_finding_ids
        ),
    )

except ValueError as exc:

    error_text = str(
        exc
    )

    assert (
        "999"
        in error_text
    )

else:

    raise AssertionError(
        "Expected provenance repair "
        "failure was not raised."
    )


assert (
    fake_model
    .structured_model
    .invoke_count
    == 2
)


print(
    "Failed repair closes safely: PASSED"
)


#
# -------------------------------------------------
# Test 3:
#
# Valid first response.
#
# No repair invocation should occur.
# -------------------------------------------------
#

print()
print(
    "TEST 3 - REPAIR NOT REQUIRED"
)
print(
    "----------------------------"
)


fake_model = FakeChatModel(
    responses=[
        valid_repaired_review,
    ]
)


review_agent = ReviewAgent(
    model=fake_model,
)


result = review_agent.review(
    research_question=(
        "Test research question?"
    ),
    findings_text=(
        "Finding ID 100: First finding.\n"
        "Finding ID 101: Second finding.\n"
        "Finding ID 102: Third finding."
    ),
    valid_finding_ids=(
        valid_finding_ids
    ),
)


assert (
    fake_model
    .structured_model
    .invoke_count
    == 1
)


assert (
    result
    == valid_repaired_review
)


print(
    "Valid response avoids repair: PASSED"
)


#
# -------------------------------------------------
# Test 4:
#
# Overlap in first response.
# Corrected second response.
#
# This verifies the second provenance invariant.
# -------------------------------------------------
#

print()
print(
    "TEST 4 - OVERLAP REPAIR"
)
print(
    "-----------------------"
)


overlapping_review = (
    ResearchQuestionReview(
        answer=(
            "Review containing overlapping "
            "provenance."
        ),
        reviewed_claims=[
            ReviewedClaim(
                claim="Overlapping claim.",
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
)


fake_model = FakeChatModel(
    responses=[
        overlapping_review,
        valid_repaired_review,
    ]
)


review_agent = ReviewAgent(
    model=fake_model,
)


result = review_agent.review(
    research_question=(
        "Test research question?"
    ),
    findings_text=(
        "Finding ID 100: First finding.\n"
        "Finding ID 101: Second finding.\n"
        "Finding ID 102: Third finding."
    ),
    valid_finding_ids=(
        valid_finding_ids
    ),
)


assert (
    fake_model
    .structured_model
    .invoke_count
    == 2
)


assert (
    result
    == valid_repaired_review
)


repair_messages = (
    fake_model
    .structured_model
    .messages_received[1]
)


repair_message_text = "\n".join(
    message.content
    for message in repair_messages
)


assert (
    "101"
    in repair_message_text
)


print(
    "Overlapping provenance repair: PASSED"
)


print()
print(
    "============================="
)
print("PASS")
print(
    "============================="
)

print(
    "Review provenance repair "
    "lifecycle behaves as expected."
)