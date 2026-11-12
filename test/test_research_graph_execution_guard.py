
from unittest.mock import (
    MagicMock,
    patch,
)

import pytest

from application.execution_lease_heartbeat import (
    ExecutionLeaseLost,
)

from application.research_job_heartbeat import (
    ResearchJobLeaseLost,
)

from graph.research_graph import (
    create_research_graph,
)


def make_node(
    name,
    calls,
    result=None,
):

    def node(
        state,
        config=None,
    ):

        calls.append(name)

        if result is not None:
            return result

        return {}

    return node


def make_graph(
    calls,
):

    node_results = {
        "select_review_question": {
            "current_review_question_id": None,
        },
        "check_pause": {
            "pause_requested": False,
        },
    }

    node_names = {
        "ResearchPlanner": "plan_research",
        "SaveResearchPlanNode": "save_research_plan",
        "SelectQuestionNode": "select_question",
        "CheckExistingSearchNode": "check_existing_search",
        "CreateSearchPlanNode": "create_search_plan",
        "SearchWebNode": "search_web",
        "SaveSearchResultsNode": "save_search_results",
        "RetrieveSourcesNode": "retrieve_sources",
        "AnalyseSourcesNode": "analyse_sources",
        "CompleteQuestionNode": "complete_question",
        "CompleteResearchNode": "complete_research",
        "SelectReviewQuestionNode": "select_review_question",
        "ReviewQuestionNode": "review_question",
        "CompleteReviewNode": "complete_review",
        "GenerateReportNode": "generate_report",
        "CompleteReportNode": "complete_report",
        "SelectResumePhaseNode": "select_resume_phase",
        "CheckPauseNode": "check_pause",
    }

    patchers = []

    for class_name, node_name in node_names.items():

        replacement = MagicMock(
            return_value=make_node(
                name=node_name,
                calls=calls,
                result=node_results.get(
                    node_name
                ),
            )
        )

        patchers.append(
            patch(
                f"graph.research_graph.{class_name}",
                replacement,
            )
        )

    for patcher in patchers:
        patcher.start()

    try:

        models = MagicMock()

        graph = create_research_graph(
            models=models,
            session_factory=MagicMock(),
            search_provider=MagicMock(),
            document_retriever=MagicMock(),
            document_extractor=MagicMock(),
        )

        return graph

    finally:

        for patcher in reversed(patchers):
            patcher.stop()


def make_state():

    return {
        "session_id": "test-session",
        "topic": "Test topic",
        "scope": None,
        "resume": True,
        "resume_phase": "researched",
        "execution_target": "review",
        "pause_requested": False,
        "research_plan": None,
        "current_question_id": None,
        "current_question": None,
        "search_required": False,
        "current_search_attempt_id": None,
        "search_plan": None,
        "search_results": [],
        "current_review_question_id": None,
        "current_review_question": None,
    }


def test_compiled_graph_executes_wrapped_nodes():

    calls = []

    graph = make_graph(
        calls=calls,
    )

    guard = MagicMock()

    result = graph.invoke(
        make_state(),
        config={
            "configurable": {
                "execution_guard": guard,
            },
        },
    )

    assert calls == [
        "select_resume_phase",
        "select_review_question",
        "complete_review",
    ]

    assert result["resume_phase"] == "researched"

    assert guard.call_count == 6


def test_execution_lease_loss_prevents_first_node():

    calls = []

    graph = make_graph(
        calls=calls,
    )

    guard = MagicMock(
        side_effect=ExecutionLeaseLost(
            "Execution lease lost."
        )
    )

    with pytest.raises(
        ExecutionLeaseLost,
    ):

        graph.invoke(
            make_state(),
            config={
                "configurable": {
                    "execution_guard": guard,
                },
            },
        )

    assert calls == []


def test_job_lease_loss_prevents_next_node():

    calls = []

    graph = make_graph(
        calls=calls,
    )

    guard = MagicMock(
        side_effect=[
            None,
            None,
            ResearchJobLeaseLost(
                "Job lease lost."
            ),
        ]
    )

    with pytest.raises(
        ResearchJobLeaseLost,
    ):

        graph.invoke(
            make_state(),
            config={
                "configurable": {
                    "execution_guard": guard,
                },
            },
        )

    assert calls == [
        "select_resume_phase",
    ]


def test_conditional_routing_preserved():

    calls = []

    graph = make_graph(
        calls=calls,
    )

    state = make_state()

    state["resume_phase"] = "completed"

    result = graph.invoke(
        state,
    )

    assert calls == [
        "select_resume_phase",
    ]

    assert result["resume_phase"] == "completed"


def test_compiled_graph_without_guard():

    calls = []

    graph = make_graph(
        calls=calls,
    )

    graph.invoke(
        make_state(),
    )

    assert calls == [
        "select_resume_phase",
        "select_review_question",
        "complete_review",
    ]
