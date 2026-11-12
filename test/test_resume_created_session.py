"""Stage 7.20D: production graph recovery from a disposable created session.

Run from the project root: python test_resume_created_session.py
Creates one new SQL session; does not alter existing sessions.
The expected second-run exception is a deliberate boundary at search planning.
"""

import threading
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

from application.research_workflow_service import ResearchWorkflowService
from control.resume_command_handler import ResumeCommandHandler
from domain.control import ControlContext
from domain.research_plan import ResearchPlan, ResearchQuestionPlan
from domain.search import SearchPlan
from graph.research_graph import create_research_graph
from models.agent_models import AgentModels
from persistence.database import SessionLocal
from persistence.research_session_repository import ResearchSessionRepository


class ExpectedResearchReached(Exception):
    """Expected boundary: graph reached search planning on second resume."""


planner_entered = threading.Event()
release_planner = threading.Event()
planner_calls = 0


class DeterministicModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "created-session-resume-test"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="unused"))]
        )

    def with_structured_output(self, schema, *, include_raw=False, **kwargs):
        if schema is ResearchPlan:
            def plan(_messages):
                global planner_calls
                planner_calls += 1
                if planner_calls != 1:
                    raise AssertionError("Research planning was executed more than once")
                planner_entered.set()
                # Deliberately no timeout: the controlling thread releases us.
                release_planner.wait()
                return ResearchPlan(
                    topic="Created session resume test",
                    questions=[
                        ResearchQuestionPlan(
                            category="test",
                            question="Does recovery from created persist the plan once?",
                            rationale="Deterministic durable-resume acceptance test.",
                        )
                    ],
                )
            return RunnableLambda(plan)

        if schema is SearchPlan:
            def stop_at_research(_messages):
                raise ExpectedResearchReached(
                    "Graph correctly resumed into research without rerunning planning"
                )
            return RunnableLambda(stop_at_research)

        # The production graph constructs summariser, reviewer and reporter
        # agents eagerly. Their schemas are legitimate during setup, but none
        # should be invoked in this bounded recovery test.
        def reject_unexpected_invocation(_messages):
            raise AssertionError(
                f"Unexpected model invocation for structured schema: {schema}"
            )

        return RunnableLambda(reject_unexpected_invocation)


class NoExternalCalls:
    def search(self, *args, **kwargs):
        raise AssertionError("Web search must not run")

    def retrieve(self, *args, **kwargs):
        raise AssertionError("Document retrieval must not run")

    def extract(self, *args, **kwargs):
        raise AssertionError("Document extraction must not run")


def read_state(session_id):
    with SessionLocal() as db:
        repository = ResearchSessionRepository(db)
        session = repository.get(session_id)
        assert session is not None
        questions = repository.get_questions(session_id)
        return (
            session.status,
            bool(session.pause_requested),
            [(q.id, q.status, q.question) for q in questions],
        )


def main():
    print("\nRESUME CREATED SESSION TEST\n===========================")

    planner_model = DeterministicModel()
    unused_model = DeterministicModel()
    models = AgentModels(
        planner=planner_model,
        researcher=unused_model,
        summariser=unused_model,
        reviewer=unused_model,
        reporter=unused_model,
        controller=unused_model,
    )
    graph = create_research_graph(
        models=models,
        session_factory=SessionLocal,
        search_provider=NoExternalCalls(),
        document_retriever=NoExternalCalls(),
        document_extractor=NoExternalCalls(),
    )
    workflow = ResearchWorkflowService(graph=graph, session_factory=SessionLocal)
    resume_handler = ResumeCommandHandler(
        workflow_service=workflow, session_factory=SessionLocal
    )

    with SessionLocal() as db:
        repository = ResearchSessionRepository(db)
        session = repository.create(topic="Created session resume test")
        session_id = session.id

    status, paused, questions = read_state(session_id)
    assert status == "created" and not paused and not questions
    print(f"TEST 1 - Created session with zero questions: PASSED ({session_id})")

    context = ControlContext(
        session_id=session_id,
        topic="Created session resume test",
        scope=None,
        status="created",
        pause_requested=False,
    )
    worker_outcome: dict[str, Any] = {}

    def first_resume():
        try:
            worker_outcome["result"] = resume_handler.execute(context=context)
        except BaseException as exc:
            worker_outcome["error"] = exc

    thread = threading.Thread(target=first_resume, daemon=True)
    thread.start()

    try:
        assert planner_entered.wait(timeout=15.0), "Planner did not start"
        status, paused, questions = read_state(session_id)
        assert status == "created" and not paused and not questions
        print("TEST 2 - Resume from created entered planner: PASSED")

        # ResumeCommandHandler cleared the flag before starting. Set it while
        # planning is in flight, so the production CheckPauseNode stops safely
        # after SaveResearchPlanNode commits.
        with SessionLocal() as db:
            ResearchSessionRepository(db).request_pause(session_id)
        assert read_state(session_id)[1] is True
    finally:
        release_planner.set()

    thread.join(timeout=60.0)
    assert not thread.is_alive(), "First resume did not return at pause boundary"
    if "error" in worker_outcome:
        raise AssertionError("First resume failed") from worker_outcome["error"]

    result = worker_outcome["result"]
    status, paused, questions = read_state(session_id)
    assert result.session_id == session_id
    assert result.status == "planned" and result.pause_requested is True
    assert status == "planned" and paused is True
    assert len(questions) == 1 and questions[0][1] == "pending"
    assert planner_calls == 1
    original_question_id = questions[0][0]
    print("TEST 3 - Plan committed once; safe pause after planning: PASSED")

    # This time resume clears the durable pause and the production graph
    # should skip planning. The deterministic search planner raises the
    # expected sentinel before any external search or retrieval can occur.
    resumed_context = ControlContext(
        session_id=session_id,
        topic="Created session resume test",
        scope=None,
        status="planned",
        pause_requested=True,
    )
    try:
        resume_handler.execute(context=resumed_context)
    except ExpectedResearchReached:
        pass
    else:
        raise AssertionError("Second resume did not reach research planning")

    status, paused, questions = read_state(session_id)
    assert not paused, "Second resume did not clear pause flag"
    assert planner_calls == 1, "Second resume repeated research planning"
    assert len(questions) == 1, "Second resume duplicated questions"
    assert questions[0][0] == original_question_id
    assert questions[0][1] == "researching"
    # Session status can remain 'planned' while question state is 'researching'.
    assert status in {"planned", "researching"}
    print("TEST 4 - Second resume skipped planning and reached research: PASSED")
    print("TEST 5 - No duplicate questions; pause cleared: PASSED")
    print("\n===========================\nPASS\n===========================")
    print(f"Disposable session ID: {session_id}")
    print("Note: second resume intentionally stops at search planning; session is not completed.")


if __name__ == "__main__":
    main()
