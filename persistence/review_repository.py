from datetime import datetime, timezone

from sqlalchemy.orm import Session

from domain.review import (
    ResearchQuestionReview,
    PersistedQuestionReview,
    PersistedReviewedClaim,
)

from persistence.models import (
    ResearchQuestion,
    QuestionReview,
    ReviewedClaimEntity,
    ReviewedClaimSupport,
    ReviewedClaimContradiction,
    ReviewContradiction,
    ReviewEvidenceGap,
)

from sqlalchemy import text

from persistence.execution_lease_repository import (
    ExecutionLease,
    ExecutionLeaseRepository,
)

from persistence.models import Finding


class ReviewRepository:

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    def exists_for_question(
        self,
        question_id: int,
    ) -> bool:

        return (
            self.db.query(QuestionReview)
            .filter(
                QuestionReview.research_question_id
                == question_id
            )
            .first()
            is not None
        )

    def save(
        self,
        question_id: int,
        review: ResearchQuestionReview,
        valid_finding_ids: set[int],
        *,
        _commit: bool = True,
    ) -> QuestionReview:

        #
        # Validate all provenance references before
        # writing anything to the database.
        #

        self._validate_finding_references(
            review=review,
            valid_finding_ids=valid_finding_ids,
        )

        question_review = QuestionReview(
            research_question_id=question_id,
            answer=review.answer,
            overall_confidence=(
                review.overall_confidence
            ),
            sufficient_evidence=(
                review.sufficient_evidence
            ),
            created_at=datetime.now(
                timezone.utc
            ),
        )

        self.db.add(
            question_review
        )

        #
        # flush() assigns the identity value without
        # committing the transaction.
        #

        self.db.flush()

        for reviewed_claim in (
            review.reviewed_claims
        ):

            claim_entity = ReviewedClaimEntity(
                question_review_id=(
                    question_review.id
                ),
                claim=reviewed_claim.claim,
                confidence=(
                    reviewed_claim.confidence
                ),
            )

            self.db.add(
                claim_entity
            )

            self.db.flush()

            for finding_id in (
                reviewed_claim
                .supporting_finding_ids
            ):

                self.db.add(
                    ReviewedClaimSupport(
                        reviewed_claim_id=(
                            claim_entity.id
                        ),
                        finding_id=finding_id,
                    )
                )

            for finding_id in (
                reviewed_claim
                .contradicting_finding_ids
            ):

                self.db.add(
                    ReviewedClaimContradiction(
                        reviewed_claim_id=(
                            claim_entity.id
                        ),
                        finding_id=finding_id,
                    )
                )

        for contradiction in (
            review.contradictions
        ):

            self.db.add(
                ReviewContradiction(
                    question_review_id=(
                        question_review.id
                    ),
                    description=contradiction,
                )
            )

        for evidence_gap in (
            review.evidence_gaps
        ):

            self.db.add(
                ReviewEvidenceGap(
                    question_review_id=(
                        question_review.id
                    ),
                    description=evidence_gap,
                )
            )

        #
        # Everything is committed together.
        #

        try:

            self.db.flush()

            if _commit:

                self.db.commit()

                self.db.refresh(
                    question_review
                )

            return question_review

        except Exception:

            self.db.rollback()

            raise


    def get_for_question(
        self,
        question_id: int,
    ) -> PersistedQuestionReview | None:

        #
        # Load the original research question.
        #
        # The Report Agent needs both the reviewed
        # evidence and the question that evidence
        # was intended to answer.
        #

        research_question = self.db.get(
            ResearchQuestion,
            question_id,
        )

        if research_question is None:

            return None

        #
        # Load the persisted review for the
        # research question.
        #

        question_review = (
            self.db.query(QuestionReview)
            .filter(
                QuestionReview.research_question_id
                == question_id
            )
            .first()
        )

        if question_review is None:

            return None

        #
        # Reconstruct the reviewed claims.
        #

        claim_entities = (
            self.db.query(
                ReviewedClaimEntity
            )
            .filter(
                ReviewedClaimEntity.question_review_id
                == question_review.id
            )
            .order_by(
                ReviewedClaimEntity.id
            )
            .all()
        )

        reviewed_claims = []

        for claim_entity in claim_entities:

            supporting_rows = (
                self.db.query(
                    ReviewedClaimSupport
                )
                .filter(
                    ReviewedClaimSupport.reviewed_claim_id
                    == claim_entity.id
                )
                .order_by(
                    ReviewedClaimSupport.finding_id
                )
                .all()
            )

            contradicting_rows = (
                self.db.query(
                    ReviewedClaimContradiction
                )
                .filter(
                    ReviewedClaimContradiction.reviewed_claim_id
                    == claim_entity.id
                )
                .order_by(
                    ReviewedClaimContradiction.finding_id
                )
                .all()
            )

            reviewed_claims.append(
                PersistedReviewedClaim(
                    id=claim_entity.id,
                    claim=claim_entity.claim,
                    confidence=(
                        claim_entity.confidence
                    ),
                    supporting_finding_ids=[
                        row.finding_id
                        for row
                        in supporting_rows
                    ],
                    contradicting_finding_ids=[
                        row.finding_id
                        for row
                        in contradicting_rows
                    ],
                )
            )

        #
        # Load review-level contradictions.
        #

        contradiction_rows = (
            self.db.query(
                ReviewContradiction
            )
            .filter(
                ReviewContradiction.question_review_id
                == question_review.id
            )
            .order_by(
                ReviewContradiction.id
            )
            .all()
        )

        #
        # Load review-level evidence gaps.
        #

        evidence_gap_rows = (
            self.db.query(
                ReviewEvidenceGap
            )
            .filter(
                ReviewEvidenceGap.question_review_id
                == question_review.id
            )
            .order_by(
                ReviewEvidenceGap.id
            )
            .all()
        )

        #
        # Convert the persistence entities into
        # the domain/read model used by the
        # reporting layer.
        #

        return PersistedQuestionReview(
            id=question_review.id,
            research_question_id=(
                research_question.id
            ),
            category=(
                research_question.category
            ),
            question=(
                research_question.question
            ),
            answer=(
                question_review.answer
            ),
            overall_confidence=(
                question_review.overall_confidence
            ),
            sufficient_evidence=(
                question_review.sufficient_evidence
            ),
            reviewed_claims=(
                reviewed_claims
            ),
            contradictions=[
                row.description
                for row
                in contradiction_rows
            ],
            evidence_gaps=[
                row.description
                for row
                in evidence_gap_rows
            ],
        )

    def get_for_session(
        self,
        session_id: str,
    ) -> list[PersistedQuestionReview]:

        #
        # Obtain the research questions in their
        # original deterministic order.
        #

        research_questions = (
            self.db.query(
                ResearchQuestion
            )
            .filter(
                ResearchQuestion.research_session_id
                == session_id
            )
            .order_by(
                ResearchQuestion.id
            )
            .all()
        )

        reviews = []

        #
        # A session may currently be only partially
        # reviewed. Only questions with persisted
        # reviews are returned.
        #

        for research_question in (
            research_questions
        ):

            review = self.get_for_question(
                research_question.id
            )

            if review is not None:

                reviews.append(
                    review
                )

        return reviews

    def _validate_finding_references(
        self,
        review: ResearchQuestionReview,
        valid_finding_ids: set[int],
    ) -> None:

        invalid_ids = set()

        #
        # First validate that every finding ID
        # referenced by the Review Agent belongs
        # to the supplied evidence set.
        #

        for claim in (
            review.reviewed_claims
        ):

            referenced_ids = (
                claim.supporting_finding_ids
                + claim.contradicting_finding_ids
            )

            for finding_id in referenced_ids:

                if (
                    finding_id
                    not in valid_finding_ids
                ):

                    invalid_ids.add(
                        finding_id
                    )

        if invalid_ids:

            invalid_text = ", ".join(
                str(value)
                for value
                in sorted(invalid_ids)
            )

            raise ValueError(
                "Review contains invalid "
                "finding references: "
                f"{invalid_text}"
            )

        #
        # A finding cannot simultaneously support
        # and contradict the same reviewed claim.
        #
        # This catches internally inconsistent
        # provenance produced by the Review Agent
        # before anything is persisted.
        #

        for claim in (
            review.reviewed_claims
        ):

            supporting_ids = set(
                claim.supporting_finding_ids
            )

            contradicting_ids = set(
                claim.contradicting_finding_ids
            )

            overlapping_ids = (
                supporting_ids
                & contradicting_ids
            )

            if overlapping_ids:

                overlap_text = ", ".join(
                    str(value)
                    for value
                    in sorted(
                        overlapping_ids
                    )
                )

                raise ValueError(
                    "Reviewed claim contains finding "
                    "references that are both "
                    "supporting and contradicting: "
                    f"{overlap_text}"
                )


        
    def save_review_fenced(
        self,
        session_id: str,
        question_id: int,
        review: ResearchQuestionReview | None,
        valid_finding_ids: set[int],
        lease: ExecutionLease,
    ) -> int:

        try:

            if lease.session_id != session_id:

                raise ValueError(
                    "Execution lease does not match "
                    "the research session."
                )

            #
            # Lock the research session and verify
            # that this worker still owns execution.
            #

            ExecutionLeaseRepository(
                self.db
            ).fence(
                lease
            )

            #
            # Lock the question and validate
            # ownership before modifying anything.
            #

            question_row = self.db.execute(
                text(
                    """
                    SELECT id, status
                    FROM dbo.research_questions
                        WITH (UPDLOCK, HOLDLOCK)
                    WHERE id = :question_id
                    AND research_session_id = :session_id
                    """
                ),
                {
                    "question_id": question_id,
                    "session_id": session_id,
                },
            ).first()

            if question_row is None:

                raise ValueError(
                    "Research question does not belong "
                    "to the execution session."
                )

            #
            # Check for a durable review inside
            # the fenced transaction.
            #

            existing = (
                self.db.query(
                    QuestionReview
                )
                .filter(
                    QuestionReview.research_question_id
                    == question_id
                )
                .first()
            )

            if existing is not None:

                if question_row.status not in (
                    "reviewing",
                    "reviewed",
                ):

                    raise ValueError(
                        "Existing review has an "
                        "unexpected question status."
                    )

                review_id = existing.id

            else:

                #
                # A new review may only be saved
                # while the question is reviewing.
                #

                if question_row.status != "reviewing":

                    raise ValueError(
                        "Only a reviewing question "
                        "can receive a new review."
                    )

                if review is None:

                    raise ValueError(
                        "No review exists and no "
                        "new review was supplied."
                    )

                #
                # Verify that every supplied finding
                # belongs to this research question.
                #

                persisted_finding_ids = set(
                    row[0]
                    for row in (
                        self.db.query(
                            Finding.id
                        )
                        .filter(
                            Finding.research_question_id
                            == question_id
                        )
                        .all()
                    )
                )

                if not valid_finding_ids.issubset(
                    persisted_finding_ids
                ):

                    raise ValueError(
                        "Review evidence contains "
                        "findings belonging to another "
                        "question or missing findings."
                    )

                #
                # Validate review references before
                # inserting any review entities.
                #

                self._validate_finding_references(
                    review=review,
                    valid_finding_ids=(
                        valid_finding_ids
                    ),
                )

                #
                # Insert the review and all associated
                # provenance records without committing.
                #

                persisted_review = self.save(
                    question_id=question_id,
                    review=review,
                    valid_finding_ids=(
                        valid_finding_ids
                    ),
                    _commit=False,
                )

                review_id = persisted_review.id

            #
            # Mark the question reviewed within
            # the same transaction.
            #

            if question_row.status != "reviewed":

                question = self.db.get(
                    ResearchQuestion,
                    question_id,
                )

                question.status = "reviewed"

                question.updated_at = (
                    datetime.now(
                        timezone.utc
                    )
                )

            #
            # Review insertion and question status
            # are committed atomically.
            #

            self.db.flush()

            self.db.commit()

            return review_id

        except Exception:

            self.db.rollback()

            raise
