
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from application.execution_lease_heartbeat import (
    ExecutionLeaseLost,
)

from application.research_job_heartbeat import (
    ResearchJobLeaseLost,
)

from nodes.review_question import (
    ReviewQuestionNode,
)

from persistence.execution_lease_repository import (
    ExecutionLease,
)


def make_lease():

    return ExecutionLease(
        session_id="test-session",
        owner="test-worker",
        version=1,
        expires_at=(
            datetime.now(timezone.utc)
            + timedelta(minutes=2)
        ),
    )


def make_state():

    return {
        "session_id": "test-session",
        "current_review_question_id": 10,
        "current_review_question": (
            "What does the evidence establish?"
        ),
    }


def make_config(
    lease,
    guard=None,
):

    configurable = {
        "execution_lease": lease,
    }

    if guard is not None:

        configurable["execution_guard"] = guard

    return {
        "configurable": configurable,
    }


@pytest.fixture
def review_environment():

    session_factory = Mock()

    db = Mock()

    session_factory.return_value.__enter__ = Mock(
        return_value=db
    )

    session_factory.return_value.__exit__ = Mock(
        return_value=None
    )

    review_agent = Mock()

    review_agent.review.return_value = (
        SimpleNamespace(
            answer="The evidence supports the claim.",
            overall_confidence=0.9,
            sufficient_evidence=True,
            reviewed_claims=[],
            contradictions=[],
            evidence_gaps=[],
        )
    )

    context_builder = Mock()

    context_builder.build.return_value = (
        "Prepared evidence context"
    )

    findings = [
        SimpleNamespace(
            id=101,
            source_id=201,
        ),
        SimpleNamespace(
            id=102,
            source_id=202,
        ),
    ]

    sources = [
        SimpleNamespace(
            id=201,
            research_session_id="test-session",
            research_question_id=10,
            title="First source",
            final_url="https://example.com/201",
            extracted_text="First source evidence.",
        ),
        SimpleNamespace(
            id=202,
            research_session_id="test-session",
            research_question_id=10,
            title="Second source",
            final_url="https://example.com/202",
            extracted_text="Second source evidence.",
        ),
    ]

    with (
        patch(
            "nodes.review_question.ReviewRepository"
        ) as review_repository_class,
        patch(
            "nodes.review_question.FindingRepository"
        ) as finding_repository_class,
        patch(
            "nodes.review_question.SourceRepository"
        ) as source_repository_class,
        patch(
            "nodes.review_question.ResearchScopeRepository"
        ) as scope_repository_class,
    ):

        scope_repository_class.return_value.get.return_value = (
            None
        )

        review_repository = (
            review_repository_class.return_value
        )

        finding_repository = (
            finding_repository_class.return_value
        )

        source_repository = (
            source_repository_class.return_value
        )

        review_repository.exists_for_question.return_value = (
            False
        )

        review_repository.save_review_fenced.return_value = (
            500
        )

        finding_repository.get_for_question.return_value = (
            findings
        )

        source_repository.get_by_ids.return_value = (
            sources
        )

        node = ReviewQuestionNode(
            session_factory=session_factory,
            review_agent=review_agent,
            context_builder=context_builder,
        )

        yield SimpleNamespace(
            node=node,
            db=db,
            session_factory=session_factory,
            review_agent=review_agent,
            context_builder=context_builder,
            review_repository=review_repository,
            finding_repository=finding_repository,
            source_repository=source_repository,
        )


def test_execution_lease_lost_before_evidence_retrieval(
    review_environment,
):

    environment = review_environment

    lease = make_lease()

    guard = Mock(
        side_effect=ExecutionLeaseLost(
            "Execution lease lost."
        )
    )

    with pytest.raises(
        ExecutionLeaseLost,
    ):

        environment.node(
            make_state(),
            make_config(
                lease,
                guard,
            ),
        )

    guard.assert_called_once()

    environment.session_factory.assert_not_called()

    environment.review_agent.review.assert_not_called()

    environment.review_repository.save_review_fenced.assert_not_called()


def test_job_lease_lost_before_review_agent(
    review_environment,
):

    environment = review_environment

    lease = make_lease()

    guard = Mock(
        side_effect=[
            None,
            ResearchJobLeaseLost(
                "Job lease lost."
            ),
        ]
    )

    with pytest.raises(
        ResearchJobLeaseLost,
    ):

        environment.node(
            make_state(),
            make_config(
                lease,
                guard,
            ),
        )

    assert guard.call_count == 2

    environment.finding_repository.get_for_question.assert_called_once_with(
        10
    )

    environment.context_builder.build.assert_called_once()

    environment.review_agent.review.assert_not_called()

    environment.review_repository.save_review_fenced.assert_not_called()


def test_execution_lease_lost_during_review_agent(
    review_environment,
):

    environment = review_environment

    lease = make_lease()

    guard = Mock(
        side_effect=[
            None,
            None,
            ExecutionLeaseLost(
                "Execution lease lost during review."
            ),
        ]
    )

    with pytest.raises(
        ExecutionLeaseLost,
    ):

        environment.node(
            make_state(),
            make_config(
                lease,
                guard,
            ),
        )

    assert guard.call_count == 3

    environment.review_agent.review.assert_called_once()

    environment.review_repository.save_review_fenced.assert_not_called()


def test_successful_review_uses_execution_lease(
    review_environment,
):

    environment = review_environment

    lease = make_lease()

    guard = Mock()

    result = environment.node(
        make_state(),
        make_config(
            lease,
            guard,
        ),
    )

    assert result == {}

    assert guard.call_count == 3

    environment.review_agent.review.assert_called_once_with(
        research_question=(
            "What does the evidence establish?"
        ),
        findings_text="Prepared evidence context",
        valid_finding_ids={
            101,
            102,
        },
        scope_definition=None,
    )

    environment.review_repository.save_review_fenced.assert_called_once_with(
        session_id="test-session",
        question_id=10,
        review=environment.review_agent.review.return_value,
        valid_finding_ids={
            101,
            102,
        },
        lease=lease,
    )


def test_existing_review_skips_review_agent(
    review_environment,
):

    environment = review_environment

    environment.review_repository.exists_for_question.return_value = (
        True
    )

    lease = make_lease()

    guard = Mock()

    result = environment.node(
        make_state(),
        make_config(
            lease,
            guard,
        ),
    )

    assert result == {}

    assert guard.call_count == 2

    environment.review_agent.review.assert_not_called()

    environment.finding_repository.get_for_question.assert_not_called()

    environment.review_repository.save_review_fenced.assert_called_once_with(
        session_id="test-session",
        question_id=10,
        review=None,
        valid_finding_ids=set(),
        lease=lease,
    )


def test_invalid_execution_guard_is_rejected(
    review_environment,
):

    environment = review_environment

    lease = make_lease()

    config = {
        "configurable": {
            "execution_lease": lease,
            "execution_guard": "not-callable",
        },
    }

    with pytest.raises(
        TypeError,
        match="Execution guard must be callable",
    ):

        environment.node(
            make_state(),
            config,
        )

    environment.session_factory.assert_not_called()

    environment.review_agent.review.assert_not_called()

    environment.review_repository.save_review_fenced.assert_not_called()



@pytest.mark.parametrize(
    "extracted_text",
    [
        "",
        " ",
        "\t\r\n ",
    ],
)
def test_invalid_source_findings_excluded_from_review(
    review_environment,
    extracted_text,
):

    environment = review_environment

    sources = (
        environment.source_repository
        .get_by_ids.return_value
    )

    sources[0].extracted_text = extracted_text

    lease = make_lease()

    result = environment.node(
        make_state(),
        make_config(lease),
    )

    assert result == {}

    environment.context_builder.build.assert_called_once()

    context_arguments = (
        environment.context_builder.build.call_args.kwargs
    )

    context_finding_ids = {
        finding.id
        for finding in context_arguments["findings"]
    }

    assert context_finding_ids == {102}

    environment.review_agent.review.assert_called_once()

    review_arguments = (
        environment.review_agent.review.call_args.kwargs
    )

    assert review_arguments["valid_finding_ids"] == {
        102,
    }

    environment.review_repository.save_review_fenced.assert_called_once()

    persistence_arguments = (
        environment.review_repository
        .save_review_fenced.call_args.kwargs
    )

    assert persistence_arguments["valid_finding_ids"] == {
        102,
    }

    assert persistence_arguments["lease"] is lease


def test_all_invalid_findings_produce_insufficient_evidence(
    review_environment,
):

    environment = review_environment

    sources = (
        environment.source_repository
        .get_by_ids.return_value
    )

    sources[0].extracted_text = ""

    sources[1].extracted_text = " \t\r\n "

    lease = make_lease()

    result = environment.node(
        make_state(),
        make_config(lease),
    )

    assert result == {}

    environment.context_builder.build.assert_not_called()

    environment.review_agent.review.assert_not_called()

    environment.review_repository.save_review_fenced.assert_called_once()

    arguments = (
        environment.review_repository
        .save_review_fenced.call_args.kwargs
    )

    review = arguments["review"]

    assert review.answer == (
        "Insufficient evidence to answer "
        "the research question."
    )

    assert review.overall_confidence == "low"

    assert review.sufficient_evidence is False

    assert review.reviewed_claims == []

    assert review.contradictions == []

    assert review.evidence_gaps == [
        (
            "No usable research findings were "
            "available for this question."
        )
    ]

    assert arguments["valid_finding_ids"] == set()

    assert arguments["lease"] is lease



def test_missing_source_prevents_review(
    review_environment,
):

    environment = review_environment

    sources = (
        environment.source_repository
        .get_by_ids.return_value
    )

    sources.pop(0)

    with pytest.raises(ValueError):

        environment.node(
            make_state(),
            make_config(
                make_lease()
            ),
        )

    environment.context_builder.build.assert_not_called()

    environment.review_agent.review.assert_not_called()

    environment.review_repository.save_review_fenced.assert_not_called()


@pytest.mark.parametrize(
    "attribute, invalid_value",
    [
        (
            "research_session_id",
            "foreign-session",
        ),
        (
            "research_question_id",
            999,
        ),
    ],
)
def test_foreign_source_prevents_review(
    review_environment,
    attribute,
    invalid_value,
):

    environment = review_environment

    sources = (
        environment.source_repository
        .get_by_ids.return_value
    )

    setattr(
        sources[0],
        attribute,
        invalid_value,
    )

    with pytest.raises(ValueError):

        environment.node(
            make_state(),
            make_config(
                make_lease()
            ),
        )

    environment.context_builder.build.assert_not_called()

    environment.review_agent.review.assert_not_called()

    environment.review_repository.save_review_fenced.assert_not_called()


def test_existing_invalid_review_cannot_be_recovered(
    review_environment,
):

    environment = review_environment

    environment.review_repository.exists_for_question.return_value = (
        True
    )

    environment.review_repository.save_review_fenced.side_effect = (
        ValueError(
            "Existing review contains invalid evidence."
        )
    )

    with pytest.raises(
        ValueError,
        match="invalid evidence",
    ):

        environment.node(
            make_state(),
            make_config(
                make_lease()
            ),
        )

    environment.finding_repository.get_for_question.assert_not_called()

    environment.context_builder.build.assert_not_called()

    environment.review_agent.review.assert_not_called()

    environment.review_repository.save_review_fenced.assert_called_once()