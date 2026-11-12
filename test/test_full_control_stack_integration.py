import threading

from typing import (
    Any,
)

from langchain_core.language_models.chat_models import (
    BaseChatModel,
)

from langchain_core.messages import (
    AIMessage,
)

from langchain_core.outputs import (
    ChatGeneration,
    ChatResult,
)

from langchain_core.runnables import (
    RunnableLambda,
)

from domain.research_plan import (
    ResearchPlan,
    ResearchQuestionPlan,
)

from domain.search import (
    SearchPlan,
)

from graph.research_graph import (
    create_research_graph,
)

from models.agent_models import (
    AgentModels,
)

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from control.control_service import (
    ControlService,
)

from control.control_context_factory import (
    ControlContextFactory,
)

from control.status_command_handler import (
    StatusCommandHandler,
)

from control.pause_command_handler import (
    PauseCommandHandler,
)

from control.resume_command_handler import (
    ResumeCommandHandler,
)

from agents.control_agent import (
    ControlAgent,
)

from models.factory import (
    ChatModelFactory,
)

from config import (
    create_model_settings,
)

from processing.control_command_validator import (
    ControlCommandValidator,
)

from processing.control_lifecycle_policy import (
    ControlLifecyclePolicy,
)


#
# -------------------------------------------------
# Expected test termination
# -------------------------------------------------
#


class ExpectedResearchReached(
    Exception
):
    pass


#
# -------------------------------------------------
# Thread coordination
# -------------------------------------------------
#
# The planner signals when it is genuinely executing
# inside the production graph.
#
# It then waits until the test has requested pause
# through ControlService.
# -------------------------------------------------
#


planner_entered = (
    threading.Event()
)

release_planner = (
    threading.Event()
)


#
# -------------------------------------------------
# Fake model infrastructure
# -------------------------------------------------
#


class FakeChatModel(BaseChatModel):

    @property
    def _llm_type(self) -> str:

        return (
            "fake-pause-control-"
            "integration-model"
        )

    def _generate(
        self,
        messages,
        stop=None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:

        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content="unused"
                    )
                )
            ]
        )

    def with_structured_output(
        self,
        schema,
        *,
        include_raw=False,
        **kwargs,
    ):

        def invoke_structured(
            messages,
        ):

            if schema is ResearchPlan:

                return ResearchPlan(
                    topic=(
                        "Control pause "
                        "integration test"
                    ),
                    questions=[
                        ResearchQuestionPlan(
                            category="test",
                            question=(
                                "What should be "
                                "researched?"
                            ),
                            rationale=(
                                "Deterministic "
                                "integration test."
                            ),
                        )
                    ],
                )

            if schema is SearchPlan:

                raise ExpectedResearchReached(
                    "Production graph reached "
                    "the search-planning stage."
                )

            raise AssertionError(
                "Unexpected structured model "
                "invocation: "
                f"{schema}"
            )

        return RunnableLambda(
            invoke_structured
        )


#
# -------------------------------------------------
# Blocking planner
# -------------------------------------------------
#
# Unlike the previous test, this model does NOT
# modify SQL itself.
#
# It merely blocks long enough for the test thread
# to issue a real pause command through
# ControlService.
# -------------------------------------------------
#


class BlockingPlannerModel(
    FakeChatModel
):

    def with_structured_output(
        self,
        schema,
        *,
        include_raw=False,
        **kwargs,
    ):

        if schema is not ResearchPlan:

            return (
                super()
                .with_structured_output(
                    schema,
                    include_raw=(
                        include_raw
                    ),
                    **kwargs,
                )
            )

        def invoke_plan(
            messages,
        ):

            print()
            print(
                "Planner entered."
            )

            planner_entered.set()


            release_planner.wait()

            print(
                "Planner released."
            )

            return ResearchPlan(
                topic=(
                    "Control pause "
                    "integration test"
                ),
                questions=[
                    ResearchQuestionPlan(
                        category="test",
                        question=(
                            "What is the purpose "
                            "of this test?"
                        ),
                        rationale=(
                            "Verify cooperative "
                            "pause through the "
                            "real control layer."
                        ),
                    )
                ],
            )

        return RunnableLambda(
            invoke_plan
        )


#
# -------------------------------------------------
# Fake external infrastructure
# -------------------------------------------------
#


class FakeSearchProvider:

    def search(
        self,
        *args,
        **kwargs,
    ):

        raise AssertionError(
            "Web search must not execute "
            "during this integration test."
        )


class FakeDocumentRetriever:

    def retrieve(
        self,
        *args,
        **kwargs,
    ):

        raise AssertionError(
            "Document retrieval must not execute "
            "during this integration test."
        )


class FakeDocumentExtractor:

    def extract(
        self,
        *args,
        **kwargs,
    ):

        raise AssertionError(
            "Document extraction must not execute "
            "during this integration test."
        )





#
# -------------------------------------------------
# Unused ControlService handlers
# -------------------------------------------------
#


class UnusedHandler:

    def execute(
        self,
        *args,
        **kwargs,
    ):

        raise AssertionError(
            "Unexpected control handler invoked."
        )


#
# -------------------------------------------------
# Build production research graph
# -------------------------------------------------
#


print()
print(
    "FULL CONTROL-STACK INTEGRATION TEST"
)

print(
    "=============================="
)


planner_model = (
    BlockingPlannerModel()
)

unused_model = (
    FakeChatModel()
)


controller_settings = (
    create_model_settings(
        "CONTROLLER"
    )
)

controller_model = (
    ChatModelFactory.create(
        controller_settings
    )
)

control_agent = (
    ControlAgent(
        model=controller_model
    )
)

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
    search_provider=(
        FakeSearchProvider()
    ),
    document_retriever=(
        FakeDocumentRetriever()
    ),
    document_extractor=(
        FakeDocumentExtractor()
    ),
)


workflow_service = (
    ResearchWorkflowService(
        graph=graph,
        session_factory=SessionLocal,
    )
)


#
# -------------------------------------------------
# Build real control handlers
# -------------------------------------------------
#


context_factory = (
    ControlContextFactory(
        SessionLocal
    )
)


status_handler = (
    StatusCommandHandler(
        SessionLocal
    )
)


pause_handler = (
    PauseCommandHandler(
        SessionLocal
    )
)


resume_handler = (
    ResumeCommandHandler(
        workflow_service=(
            workflow_service
        ),
        session_factory=(
            SessionLocal
        ),
    )
)


unused_handler = (
    UnusedHandler()
)


#
# -------------------------------------------------
# Build ControlService
# -------------------------------------------------
#


control_service = (
    ControlService(
        control_agent=(
            control_agent
        ),
        context_factory=(
            context_factory
        ),
        command_validator=(
            ControlCommandValidator()
        ),
        lifecycle_policy=(
            ControlLifecyclePolicy()
        ),
        status_handler=(
            status_handler
        ),
        help_handler=(
            unused_handler
        ),
        start_research_handler=(
            unused_handler
        ),
        resume_handler=(
            resume_handler
        ),
        generate_report_handler=(
            unused_handler
        ),
        add_question_handler=(
            unused_handler
        ),
        modify_scope_handler=(
            unused_handler
        ),
        deeper_research_handler=(
            unused_handler
        ),
        counter_evidence_handler=(
            unused_handler
        ),
        pause_handler=(
            pause_handler
        ),
    )
)


#
# -------------------------------------------------
# Workflow thread result
# -------------------------------------------------
#


workflow_result = None
workflow_error = None


def run_workflow():

    global workflow_result
    global workflow_error

    try:

        workflow_result = (
            workflow_service.start(
                topic=(
                    "Control pause "
                    "integration test"
                ),
            )
        )

    except Exception as ex:

        workflow_error = ex


#
# -------------------------------------------------
# TEST 1
#
# Start production graph and wait until the planner
# is genuinely executing.
# -------------------------------------------------
#


print()
print(
    "TEST 1 - WORKFLOW IN FLIGHT"
)

print(
    "---------------------------"
)


workflow_thread = (
    threading.Thread(
        target=run_workflow,
        daemon=True,
    )
)


workflow_thread.start()


entered = (
    planner_entered.wait(
        timeout=10.0
    )
)


assert entered is True


print(
    "Production planner is running: PASSED"
)


#
# -------------------------------------------------
# Find the session created by ResearchWorkflowService.
# -------------------------------------------------
#


from persistence.models import (
    ResearchSession,
)


with SessionLocal() as db:

    session = (
        db.query(
            ResearchSession
        )
        .filter(
            ResearchSession.topic
            ==
            "Control pause integration test",
            ResearchSession.status
            ==
            "planning",
        )
        .order_by(
            ResearchSession.created_at
            .desc()
        )
        .first()
    )

    if session is None:

        raise AssertionError(
            "Could not locate the "
            "in-flight research session."
        )

    session_id = session.id


print(
    f"Session ID: {session_id}"
)


#
# -------------------------------------------------
# TEST 2
#
# Pause through ControlService while planning is
# genuinely in flight.
# -------------------------------------------------
#


print()
print(
    "TEST 2 - CONTROL PAUSE"
)

print(
    "----------------------"
)


try:

    pause_result = (
        control_service.execute(
            user_message="hold it there",
            session_id=session_id,
        )
    )

except Exception:

    release_planner.set()
    raise


assert (
    pause_result.operation
    == "pause"
)


assert (
    pause_result.success
    is True
)


assert (
    pause_result.pause
    is not None
)


assert (
    pause_result.pause.pause_requested
    is True
)


print(
    "ControlService accepted pause: PASSED"
)


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    paused_session = (
        repository.get(
            session_id
        )
    )


assert paused_session is not None


assert (
    paused_session.status
    == "planning"
)


assert (
    paused_session.pause_requested
    is True
)


print(
    "SQL pause_requested=True: PASSED"
)

print(
    "Lifecycle remains planning: PASSED"
)


#
# -------------------------------------------------
# TEST 3
#
# Release planning.
#
# The plan should persist, then the production
# check_pause_planning node should observe the
# durable pause request and terminate the graph.
# -------------------------------------------------
#


print()
print(
    "TEST 3 - SAFE BOUNDARY"
)

print(
    "----------------------"
)


release_planner.set()


workflow_thread.join(
    timeout=60.0
)


assert (
    workflow_thread.is_alive()
    is False
)


if workflow_error is not None:

    raise workflow_error


assert workflow_result is not None


print(
    "Workflow returned at pause boundary: PASSED"
)


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    boundary_session = (
        repository.get(
            session_id
        )
    )

    questions = (
        repository.get_questions(
            session_id
        )
    )


assert boundary_session is not None


assert (
    boundary_session.status
    == "planned"
)


assert (
    boundary_session.pause_requested
    is True
)


assert len(questions) == 1


assert (
    questions[0].status
    == "pending"
)


print(
    "Plan committed before suspension: PASSED"
)

print(
    "Session status is planned: PASSED"
)

print(
    "Question remains pending: PASSED"
)

print(
    "Pause remains durable: PASSED"
)


assert (
    workflow_result.graph_result[
        "pause_requested"
    ]
    is True
)


assert (
    workflow_result.graph_result.get(
        "current_question_id"
    )
    is None
)


print(
    "Production graph observed pause: PASSED"
)

print(
    "Research did not start: PASSED"
)


#
# -------------------------------------------------
# TEST 4
#
# Status through ControlService.
# -------------------------------------------------
#


print()
print(
    "TEST 4 - CONTROL STATUS"
)

print(
    "-----------------------"
)


status_result = (
    control_service.execute(
        user_message="what's happening?",
        session_id=session_id,
    )
)


assert (
    status_result.operation
    == "status"
)


assert (
    status_result.success
    is True
)


assert (
    status_result.status
    is not None
)


assert (
    status_result.status.status
    == "planned"
)


assert (
    status_result.status.pause_requested
    is True
)

assert (
    status_result.message
    ==
    "Research is paused at a safe "
    "workflow boundary. "
    "Research planning is complete. "
    "1 question is pending."
)

print(
    "Conversational status intent "
    "resolved correctly: PASSED"
)

print(
    "Rich status message returned: PASSED"
)

print(
    "Control status is planned: PASSED"
)

print(
    "Control status reports "
    "pause_requested=True: PASSED"
)


#
# -------------------------------------------------
# TEST 5
#
# Resume through ControlService.
#
# ResumeCommandHandler must:
#
#   1. clear pause_requested
#   2. call ResearchWorkflowService.resume()
#   3. production graph resumes from planned
#   4. select pending question
#   5. enter research
#
# Fake SearchPlan deliberately raises once that
# point is reached.
# -------------------------------------------------
#


print()
print(
    "TEST 5 - CONTROL RESUME"
)

print(
    "-----------------------"
)


research_reached = False


try:

    control_service.execute(
        user_message="carry on",
        session_id=session_id,
    )

except ExpectedResearchReached:

    research_reached = True


assert research_reached is True


print(
    "Production graph resumed into "
    "research: PASSED"
)


#
# -------------------------------------------------
# Verify durable resume state.
# -------------------------------------------------
#


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    resumed_session = (
        repository.get(
            session_id
        )
    )

    resumed_questions = (
        repository.get_questions(
            session_id
        )
    )


assert resumed_session is not None


assert (
    resumed_session.pause_requested
    is False
)


assert len(
    resumed_questions
) == 1


resumed_question = (
    resumed_questions[0]
)


assert (
    resumed_question.status
    == "researching"
)

#
# -------------------------------------------------
# TEST 6
#
# Conversational status after resume.
#
# The workflow deliberately terminated at search
# planning. The coarse session lifecycle remains
# planned, while the selected question has already
# transitioned to researching.
# -------------------------------------------------
#


print()
print(
    "TEST 6 - STATUS AFTER RESUME"
)

print(
    "----------------------------"
)


status_after_resume = (
    control_service.execute(
        user_message="where are we?",
        session_id=session_id,
    )
)


assert (
    status_after_resume.operation
    == "status"
)


assert (
    status_after_resume.success
    is True
)


assert (
    status_after_resume.status
    is not None
)

#
# The coarse session lifecycle remains planned
# because the deliberate SearchPlan exception
# occurs before a later session-level transition.
#
# The question lifecycle provides the finer-grained
# indication that research has actually started.
#

assert (
    status_after_resume.status.status
    == "planned"
)

assert (
    status_after_resume.status.pending_questions
    == 0
)

assert (
    status_after_resume.status.researching_questions
    == 1
)

assert (
    status_after_resume.status.researched_questions
    == 0
)

assert (
    status_after_resume.status.pause_requested
    is False
)

assert (
    status_after_resume.message
    ==
    "Research is in progress. "
    "0 of 1 questions have been researched."
)


print(
    "Conversational status resolved "
    "after resume: PASSED"
)

print(
    "Authoritative session status "
    "remains planned: PASSED"
)

print(
    "Question status reports active "
    "research: PASSED"
)

print(
    "Status reports pause cleared: PASSED"
)

print(
    "Effective research progress "
    "message: PASSED"
)

print(
    "Pause request cleared before "
    "resume: PASSED"
)

print(
    "Completed planning not replayed: PASSED"
)

print(
    "Question transitioned "
    "pending -> researching: PASSED"
)


print()
print(
    "=============================="
)

print(
    "PASS"
)

print(
    "=============================="
)

print(
    "The real control layer requested a "
    "cooperative pause while the production "
    "LangGraph was executing, the graph stopped "
    "at its next durable boundary, status exposed "
    "the suspended state, and resume cleared the "
    "pause before continuing from durable state."
)