
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

from nodes.analyse_sources import (
    AnalyseSourcesNode,
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


def make_source(source_id):

    return SimpleNamespace(
        id=source_id,
        title=f"Source {source_id}",
        final_url=f"https://example.com/{source_id}",
        extracted_text=f"Content for source {source_id}",
    )


def make_state():

    return {
        "session_id": "test-session",
        "current_question_id": 10,
        "current_question": "What is the research answer?",
    }


def make_analysis():

    return SimpleNamespace(
        summary="Research summary",
        findings=[
            SimpleNamespace(
                claim="Research finding",
                evidence="Supporting evidence",
                relevance=0.9,
                confidence=0.9,
            ),
        ],
    )


def make_node(
    sources,
    execution_guard=None,
    existing_source_ids=None,
):

    if existing_source_ids is None:

        existing_source_ids = set()

    session_factory = Mock()

    session_factory.return_value.__enter__ = Mock(
        return_value=Mock()
    )

    session_factory.return_value.__exit__ = Mock(
        return_value=False
    )

    source_repository = Mock()

    source_repository.get_for_question.return_value = (
        sources
    )

    finding_repository = Mock()

    finding_repository.analysis_exists.side_effect = (
        lambda source_id, question_id: (
            source_id in existing_source_ids
        )
    )

    summariser = Mock()

    summariser.analyse.return_value = make_analysis()

    context_builder = Mock()

    context_builder.build.return_value = (
        "Selected source context",
        3,
        2,
    )

    node = AnalyseSourcesNode(
        session_factory=session_factory,
        summariser=summariser,
        context_builder=context_builder,
    )

    config = {
        "configurable": {
            "execution_lease": make_lease(),
        }
    }

    if execution_guard is not None:

        config["configurable"]["execution_guard"] = (
            execution_guard
        )

    return (
        node,
        config,
        summariser,
        context_builder,
        source_repository,
        finding_repository,
    )


@pytest.fixture
def repository_patches():

    with (
        patch(
            "nodes.analyse_sources.SourceRepository"
        ) as source_repository_class,
        patch(
            "nodes.analyse_sources.FindingRepository"
        ) as finding_repository_class,
    ):

        yield (
            source_repository_class,
            finding_repository_class,
        )


def configure_repositories(
    repository_patches,
    source_repository,
    finding_repository,
):

    source_repository_class, finding_repository_class = (
        repository_patches
    )

    source_repository_class.return_value = (
        source_repository
    )

    finding_repository_class.return_value = (
        finding_repository
    )


def test_execution_lease_lost_before_processing(
    repository_patches,
):

    guard = Mock(
        side_effect=ExecutionLeaseLost(
            "Execution lease lost."
        )
    )

    (
        node,
        config,
        summariser,
        context_builder,
        source_repository,
        finding_repository,
    ) = make_node(
        sources=[make_source(1)],
        execution_guard=guard,
    )

    configure_repositories(
        repository_patches,
        source_repository,
        finding_repository,
    )

    with pytest.raises(
        ExecutionLeaseLost,
    ):

        node(
            make_state(),
            config,
        )

    summariser.analyse.assert_not_called()

    finding_repository.save_analysis.assert_not_called()


def test_job_lease_lost_before_llm(
    repository_patches,
):

    guard = Mock(
        side_effect=[
            None,
            None,
            ResearchJobLeaseLost(
                "Job lease lost."
            ),
        ]
    )

    (
        node,
        config,
        summariser,
        context_builder,
        source_repository,
        finding_repository,
    ) = make_node(
        sources=[make_source(1)],
        execution_guard=guard,
    )

    configure_repositories(
        repository_patches,
        source_repository,
        finding_repository,
    )

    with pytest.raises(
        ResearchJobLeaseLost,
    ):

        node(
            make_state(),
            config,
        )

    context_builder.build.assert_called_once()

    summariser.analyse.assert_not_called()

    finding_repository.save_analysis.assert_not_called()


def test_execution_lease_lost_during_llm(
    repository_patches,
):

    guard = Mock(
        side_effect=[
            None,
            None,
            None,
            ExecutionLeaseLost(
                "Execution lease lost during analysis."
            ),
        ]
    )

    (
        node,
        config,
        summariser,
        context_builder,
        source_repository,
        finding_repository,
    ) = make_node(
        sources=[make_source(1)],
        execution_guard=guard,
    )

    configure_repositories(
        repository_patches,
        source_repository,
        finding_repository,
    )

    with pytest.raises(
        ExecutionLeaseLost,
    ):

        node(
            make_state(),
            config,
        )

    summariser.analyse.assert_called_once()

    finding_repository.save_analysis.assert_not_called()


def test_ordinary_llm_failure_continues_to_next_source(
    repository_patches,
):

    (
        node,
        config,
        summariser,
        context_builder,
        source_repository,
        finding_repository,
    ) = make_node(
        sources=[
            make_source(1),
            make_source(2),
        ],
    )

    configure_repositories(
        repository_patches,
        source_repository,
        finding_repository,
    )

    summariser.analyse.side_effect = [
        RuntimeError(
            "Temporary model failure."
        ),
        make_analysis(),
    ]

    result = node(
        make_state(),
        config,
    )

    assert result == {}

    assert summariser.analyse.call_count == 2

    finding_repository.save_analysis.assert_called_once()

    assert (
        finding_repository.save_analysis.call_args.kwargs[
            "source_id"
        ]
        == 2
    )


def test_previously_analysed_source_is_skipped(
    repository_patches,
):

    (
        node,
        config,
        summariser,
        context_builder,
        source_repository,
        finding_repository,
    ) = make_node(
        sources=[
            make_source(1),
            make_source(2),
        ],
        existing_source_ids={1},
    )

    configure_repositories(
        repository_patches,
        source_repository,
        finding_repository,
    )

    result = node(
        make_state(),
        config,
    )

    assert result == {}

    summariser.analyse.assert_called_once()

    finding_repository.save_analysis.assert_called_once()

    assert (
        finding_repository.save_analysis.call_args.kwargs[
            "source_id"
        ]
        == 2
    )


def test_successful_analysis_uses_execution_lease(
    repository_patches,
):

    guard = Mock()

    (
        node,
        config,
        summariser,
        context_builder,
        source_repository,
        finding_repository,
    ) = make_node(
        sources=[make_source(1)],
        execution_guard=guard,
    )

    configure_repositories(
        repository_patches,
        source_repository,
        finding_repository,
    )

    result = node(
        make_state(),
        config,
    )

    assert result == {}

    summariser.analyse.assert_called_once()

    finding_repository.save_analysis.assert_called_once()

    arguments = (
        finding_repository.save_analysis.call_args.kwargs
    )

    assert arguments["source_id"] == 1

    assert arguments["question_id"] == 10

    assert (
        arguments["lease"]
        is config["configurable"]["execution_lease"]
    )

    assert arguments["analysis"] is not None

    assert guard.call_count == 5
