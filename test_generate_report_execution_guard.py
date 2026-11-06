
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

from nodes.generate_report import (
    GenerateReportNode,
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
        "topic": "Quantum computing and Bitcoin",
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
def report_environment():

    session_factory = Mock()

    db = Mock()

    session_factory.return_value.__enter__ = Mock(
        return_value=db
    )

    session_factory.return_value.__exit__ = Mock(
        return_value=None
    )

    report_agent = Mock()

    report_agent.generate.return_value = (
        SimpleNamespace(
            title="Research Report",
            executive_summary="Executive summary",
            sections=[],
            conclusions="Conclusions",
            limitations=[],
        )
    )

    context_builder = Mock()

    context_builder.build.return_value = (
        "Prepared reviewed evidence"
    )

    validator = Mock()

    reviews = [
        SimpleNamespace(
            id=10,
            reviewed_claims=[
                SimpleNamespace(id=101),
                SimpleNamespace(id=102),
            ],
        ),
        SimpleNamespace(
            id=11,
            reviewed_claims=[
                SimpleNamespace(id=103),
            ],
        ),
    ]

    with (
        patch(
            "nodes.generate_report.ReportRepository"
        ) as report_repository_class,
        patch(
            "nodes.generate_report.ResearchSessionRepository"
        ) as session_repository_class,
        patch(
            "nodes.generate_report.ReviewRepository"
        ) as review_repository_class,
    ):

        report_repository = (
            report_repository_class.return_value
        )

        session_repository = (
            session_repository_class.return_value
        )

        review_repository = (
            review_repository_class.return_value
        )

        report_repository.exists_for_session.return_value = (
            False
        )

        report_repository.save_report_fenced.return_value = (
            500
        )

        session_repository.has_unfinished_research_questions.return_value = (
            False
        )

        session_repository.has_unfinished_review_questions.return_value = (
            False
        )

        review_repository.get_for_session.return_value = (
            reviews
        )

        node = GenerateReportNode(
            session_factory=session_factory,
            report_agent=report_agent,
            context_builder=context_builder,
            validator=validator,
        )

        yield SimpleNamespace(
            node=node,
            session_factory=session_factory,
            report_agent=report_agent,
            context_builder=context_builder,
            validator=validator,
            report_repository=report_repository,
            session_repository=session_repository,
            review_repository=review_repository,
        )


def test_execution_lease_lost_before_database_access(
    report_environment,
):

    environment = report_environment

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
                make_lease(),
                guard,
            ),
        )

    guard.assert_called_once()

    environment.session_factory.assert_not_called()

    environment.report_agent.generate.assert_not_called()

    environment.report_repository.save_report_fenced.assert_not_called()


def test_job_lease_lost_before_reporting_starts(
    report_environment,
):

    environment = report_environment

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
                make_lease(),
                guard,
            ),
        )

    assert guard.call_count == 2

    environment.session_repository.begin_reporting_fenced.assert_not_called()

    environment.report_agent.generate.assert_not_called()

    environment.report_repository.save_report_fenced.assert_not_called()


def test_execution_lease_lost_during_report_generation(
    report_environment,
):

    environment = report_environment

    guard = Mock(
        side_effect=[
            None,
            None,
            None,
            ExecutionLeaseLost(
                "Execution lease lost during generation."
            ),
        ]
    )

    with pytest.raises(
        ExecutionLeaseLost,
    ):

        environment.node(
            make_state(),
            make_config(
                make_lease(),
                guard,
            ),
        )

    assert guard.call_count == 4

    environment.report_agent.generate.assert_called_once()

    environment.validator.validate_claim_references.assert_not_called()

    environment.report_repository.save_report_fenced.assert_not_called()


def test_job_lease_lost_after_report_validation(
    report_environment,
):

    environment = report_environment

    guard = Mock(
        side_effect=[
            None,
            None,
            None,
            None,
            ResearchJobLeaseLost(
                "Job lease lost after validation."
            ),
        ]
    )

    with pytest.raises(
        ResearchJobLeaseLost,
    ):

        environment.node(
            make_state(),
            make_config(
                make_lease(),
                guard,
            ),
        )

    assert guard.call_count == 5

    environment.report_agent.generate.assert_called_once()

    environment.validator.validate_claim_references.assert_called_once()

    environment.report_repository.save_report_fenced.assert_not_called()


def test_successful_report_uses_execution_lease(
    report_environment,
):

    environment = report_environment

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

    assert guard.call_count == 5

    environment.session_repository.begin_reporting_fenced.assert_called_once_with(
        session_id="test-session",
        lease=lease,
    )

    environment.report_agent.generate.assert_called_once_with(
        topic="Quantum computing and Bitcoin",
        reviewed_evidence="Prepared reviewed evidence",
    )

    environment.validator.validate_claim_references.assert_called_once_with(
        report=environment.report_agent.generate.return_value,
        valid_reviewed_claim_ids={
            101,
            102,
            103,
        },
    )

    environment.report_repository.save_report_fenced.assert_called_once_with(
        session_id="test-session",
        report=environment.report_agent.generate.return_value,
        lease=lease,
    )


def test_existing_report_skips_report_agent(
    report_environment,
):

    environment = report_environment

    environment.report_repository.exists_for_session.return_value = (
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

    environment.session_repository.begin_reporting_fenced.assert_not_called()

    environment.review_repository.get_for_session.assert_not_called()

    environment.report_agent.generate.assert_not_called()

    environment.report_repository.save_report_fenced.assert_called_once_with(
        session_id="test-session",
        report=None,
        lease=lease,
    )


def test_invalid_execution_guard_is_rejected(
    report_environment,
):

    environment = report_environment

    config = {
        "configurable": {
            "execution_lease": make_lease(),
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

    environment.report_agent.generate.assert_not_called()

    environment.report_repository.save_report_fenced.assert_not_called()
