from agents.control_agent import (
    ControlAgent,
)

from config import settings

from control.control_context_factory import (
    ControlContextFactory,
)

from control.control_service import (
    ControlService,
)

from control.status_command_handler import (
    StatusCommandHandler,
)

from control.help_command_handler import (
    HelpCommandHandler,
)

from control.start_research_command_handler import (
    StartResearchCommandHandler,
)

from control.resume_command_handler import (
    ResumeCommandHandler,
)

from control.generate_report_command_handler import (
    GenerateReportCommandHandler,
)

from control.add_question_command_handler import (
    AddQuestionCommandHandler,
)

from control.modify_scope_command_handler import (
    ModifyScopeCommandHandler,
)

from control.deeper_research_command_handler import (
    DeeperResearchCommandHandler,
)

from control.counter_evidence_command_handler import (
    CounterEvidenceCommandHandler,
)

from processing.control_command_validator import (
    ControlCommandValidator,
)

from processing.control_lifecycle_policy import (
    ControlLifecyclePolicy,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from models.factory import (
    ChatModelFactory,
)

from models.agent_models import (
    AgentModels,
)

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from extraction.html import (
    HtmlDocumentExtractor,
)

from retrieval.http import (
    HttpDocumentRetriever,
)

from security.url_validator import (
    UrlValidator,
)

from search.duckduckgo import (
    DuckDuckGoSearchProvider,
)

search_provider = (
    DuckDuckGoSearchProvider()
)

from graph.research_graph import (
    create_research_graph,
)


print()
print("CONTROL MODIFY SCOPE TEST")
print("=========================")


#
# -------------------------------------------------
# Model construction.
# -------------------------------------------------
#

factory = ChatModelFactory()


agent_models = AgentModels(
    planner=factory.create(
        settings.planner_model
    ),
    researcher=factory.create(
        settings.researcher_model
    ),
    summariser=factory.create(
        settings.summariser_model
    ),
    reviewer=factory.create(
        settings.reviewer_model
    ),
    reporter=factory.create(
        settings.reporter_model
    ),
    controller=factory.create(
        settings.controller_model
    ),
)


#
# -------------------------------------------------
# Workflow service.
#
# The modify_scope operation does not execute the
# research workflow, but ControlService requires
# handlers that depend on this service.
#
# Use the same workflow-service construction used
# by your existing control tests here.
# -------------------------------------------------
#

#
# IMPORTANT:
#
# Replace the following line with the existing
# ResearchWorkflowService construction from your
# latest control test.
#
# Do not run this file until that construction has
# been copied here.
#

url_validator = UrlValidator()

document_retriever = (
    HttpDocumentRetriever(
        url_validator=url_validator,
    )
)

document_extractor = (
    HtmlDocumentExtractor()
)

graph = create_research_graph(
    models=agent_models,
    session_factory=SessionLocal,
    search_provider=search_provider,
    document_retriever=document_retriever,
    document_extractor=document_extractor,
)

#workflow_service: ResearchWorkflowService
workflow_service = (
    ResearchWorkflowService(
        graph=graph,
        session_factory=SessionLocal,
    )
)

#
# -------------------------------------------------
# Create an isolated research session.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        repository.create(
            topic=(
                "The effect of Bitcoin mining "
                "on energy systems"
            )
        )
    )

    session_id = research_session.id

    repository.set_status(
        session_id=session_id,
        status="researching",
    )


print()
print(
    f"Test session: {session_id}"
)


#
# -------------------------------------------------
# Construct ControlService.
# -------------------------------------------------
#

control_service = ControlService(

    control_agent=(
        ControlAgent(
            model=agent_models.controller,
        )
    ),

    context_factory=(
        ControlContextFactory(
            session_factory=SessionLocal,
        )
    ),

    command_validator=(
        ControlCommandValidator()
    ),

    lifecycle_policy=(
        ControlLifecyclePolicy()
    ),

    status_handler=(
        StatusCommandHandler(
            session_factory=SessionLocal,
        )
    ),

    help_handler=(
        HelpCommandHandler()
    ),

    start_research_handler=(
        StartResearchCommandHandler(
            workflow_service=workflow_service,
            session_factory=SessionLocal,
        )
    ),

    resume_handler=(
        ResumeCommandHandler(
            workflow_service=workflow_service,
            session_factory=SessionLocal,
        )
    ),

    generate_report_handler=(
        GenerateReportCommandHandler(
            workflow_service=workflow_service,
            session_factory=SessionLocal,
        )
    ),

    add_question_handler=(
        AddQuestionCommandHandler(
            session_factory=SessionLocal,
        )
    ),

    modify_scope_handler=(
        ModifyScopeCommandHandler(
            session_factory=SessionLocal,
        )
    ),

    deeper_research_handler=(
        DeeperResearchCommandHandler(
            session_factory=SessionLocal,
        )
    ),

    counter_evidence_handler=(
        CounterEvidenceCommandHandler(
            session_factory=SessionLocal,
        )
    ),
)


#
# -------------------------------------------------
# Execute natural-language request.
# -------------------------------------------------
#

print()
print("USER REQUEST")
print("------------")

user_message = (
    "Change the scope of this research to focus "
    "specifically on the economic effects of "
    "Bitcoin mining on electricity markets, "
    "including electricity pricing and grid "
    "incentives."
)

print(user_message)


print()
print("EXECUTING CONTROL AGENT")
print("-----------------------")


result = control_service.execute(
    user_message=user_message,
    session_id=session_id,
)


#
# -------------------------------------------------
# Validate ControlResult.
# -------------------------------------------------
#

print()
print("CONTROL RESULT")
print("--------------")

print(
    f"Operation: {result.operation}"
)

print(
    f"Success:   {result.success}"
)

print(
    f"Message:   {result.message}"
)


assert result.operation == "modify_scope"

assert result.success is True

assert result.scope is not None

assert result.scope.session_id == session_id

assert result.scope.status == "researching"


print()
print("Returned scope:")
print(result.scope.scope)


#
# -------------------------------------------------
# Verify durable SQL state.
# -------------------------------------------------
#

print()
print("VERIFYING SQL")
print("-------------")


with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    persisted = repository.get(
        session_id
    )

    assert persisted is not None

    assert persisted.scope is not None

    assert (
        persisted.scope
        == result.scope.scope
    )

    assert persisted.status == "researching"

    assert persisted.topic == (
        "The effect of Bitcoin mining "
        "on energy systems"
    )


print(
    "Persisted scope:"
)

print(
    persisted.scope
)


#
# The fundamental topic must remain unchanged.
#

assert persisted.topic == (
    "The effect of Bitcoin mining "
    "on energy systems"
)


print()
print(
    "Topic remained unchanged: PASSED"
)

print(
    "Scope persisted to SQL: PASSED"
)

print(
    "Control Agent selected modify_scope: PASSED"
)


#
# -------------------------------------------------
# TEST 2
# Extend the existing scope.
# -------------------------------------------------
#

print()
print("EXTENDING EXISTING SCOPE")
print("------------------------")


user_message = (
    "Keep the existing scope, but also include "
    "the effects on renewable-energy investment."
)


print()
print("USER REQUEST")
print("------------")
print(user_message)


result = control_service.execute(
    user_message=user_message,
    session_id=session_id,
)


assert result.operation == "modify_scope"
assert result.success is True
assert result.scope is not None


print()
print("Returned replacement scope:")
print(result.scope.scope)


#
# -------------------------------------------------
# Verify the complete replacement was persisted.
# -------------------------------------------------
#

with SessionLocal() as db:

    repository = (
        ResearchSessionRepository(db)
    )

    persisted = repository.get(
        session_id
    )

    assert persisted is not None
    assert persisted.scope is not None

    assert (
        persisted.scope
        == result.scope.scope
    )


print()
print("Persisted replacement scope:")
print(persisted.scope)


#
# The new scope should retain the important
# concepts from the previous scope while adding
# renewable-energy investment.
#
# We deliberately test concepts rather than exact
# wording because the Control Agent may paraphrase.
#

scope_lower = persisted.scope.lower()


assert "electricity" in scope_lower

assert (
    "pricing" in scope_lower
    or "price" in scope_lower
)

assert "grid" in scope_lower

assert "renewable" in scope_lower

assert "investment" in scope_lower


#
# Fundamental topic must still remain unchanged.
#

assert persisted.topic == (
    "The effect of Bitcoin mining "
    "on energy systems"
)


print()
print(
    "Existing scope retained: PASSED"
)

print(
    "Requested scope extension added: PASSED"
)

print(
    "Topic remained unchanged: PASSED"
)

print()
print("=========================")
print("PASS")
print("=========================")

print(
    "Natural-language scope modification "
    "completed successfully."
)