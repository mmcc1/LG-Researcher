
from unittest import TestCase
from unittest.mock import (
    MagicMock,
    patch,
)

from nodes.review_question import (
    ReviewQuestionNode,
)


class FakeExecutionLease:

    def __init__(
        self,
        session_id: str,
    ):

        self.session_id = session_id


class ReviewQuestionNoFindingsTests(TestCase):

    def test_no_findings_persists_insufficient_evidence_review(
        self,
    ):

        session_id = "test-session"
        question_id = 330

        lease = FakeExecutionLease(
            session_id=session_id,
        )

        execution_guard = MagicMock()

        db = MagicMock()

        session_context = MagicMock()
        session_context.__enter__.return_value = db

        session_factory = MagicMock(
            return_value=session_context,
        )

        review_agent = MagicMock()
        context_builder = MagicMock()

        state = {
            "session_id": session_id,
            "current_review_question_id": question_id,
            "current_review_question": (
                "How does drag influence structural "
                "stress and material fatigue?"
            ),
        }

        config = {
            "configurable": {
                "execution_lease": lease,
                "execution_guard": execution_guard,
            }
        }

        with (
            patch(
                "nodes.review_question.ExecutionLease",
                FakeExecutionLease,
            ),
            patch(
                "nodes.review_question.ReviewRepository"
            ) as review_repository_class,
            patch(
                "nodes.review_question.FindingRepository"
            ) as finding_repository_class,
            patch(
                "nodes.review_question.SourceRepository"
            ) as source_repository_class,
        ):

            review_repository = (
                review_repository_class.return_value
            )

            review_repository.exists_for_question.return_value = (
                False
            )

            review_repository.save_review_fenced.return_value = (
                106
            )

            finding_repository = (
                finding_repository_class.return_value
            )

            finding_repository.get_for_question.return_value = (
                []
            )

            node = ReviewQuestionNode(
                session_factory=session_factory,
                review_agent=review_agent,
                context_builder=context_builder,
            )

            result = node(
                state=state,
                config=config,
            )

            self.assertEqual(
                result,
                {},
            )

            review_agent.review.assert_not_called()

            context_builder.build.assert_not_called()

            source_repository = (
                source_repository_class.return_value
            )

            source_repository.get_by_ids.assert_not_called()

            review_repository.save_review_fenced.assert_called_once()

            arguments = (
                review_repository
                .save_review_fenced
                .call_args.kwargs
            )

            self.assertEqual(
                arguments["session_id"],
                session_id,
            )

            self.assertEqual(
                arguments["question_id"],
                question_id,
            )

            self.assertIs(
                arguments["lease"],
                lease,
            )

            self.assertEqual(
                arguments["valid_finding_ids"],
                set(),
            )

            review = arguments["review"]

            self.assertEqual(
                review.reviewed_claims,
                [],
            )

            self.assertEqual(
                review.contradictions,
                [],
            )

            self.assertEqual(
                review.overall_confidence,
                "low",
            )

            self.assertFalse(
                review.sufficient_evidence
            )

            self.assertTrue(
                review.evidence_gaps
            )

            self.assertEqual(
                execution_guard.call_count,
                3,
            )
