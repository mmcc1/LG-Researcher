from config import settings

from graph.research_graph import (
    create_research_graph,
)

from persistence.database import (
    SessionLocal,
)

from models.agent_models import (
    AgentModels,
)

from models.factory import (
    ChatModelFactory,
)

from search.duckduckgo import (
    DuckDuckGoSearchProvider,
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

from agents.control_agent import (
    ControlAgent,
)

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from control.control_context_factory import (
    ControlContextFactory,
)

from control.control_service import (
    ControlService,
)

from control.generate_report_command_handler import (
    GenerateReportCommandHandler,
)

from control.help_command_handler import (
    HelpCommandHandler,
)

from control.resume_command_handler import (
    ResumeCommandHandler,
)

from control.start_research_command_handler import (
    StartResearchCommandHandler,
)

from control.status_command_handler import (
    StatusCommandHandler,
)

from processing.control_command_validator import (
    ControlCommandValidator,
)

from processing.control_lifecycle_policy import (
    ControlLifecyclePolicy,
)


SESSION_ID = (
    "8b89d73a-c2b5-4b15-a6c5-bb71e43064b5"
)


#
# Infrastructure
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

search_provider = (
    DuckDuckGoSearchProvider()
)


#
# Models
#

agent_models = AgentModels(

    planner=ChatModelFactory.create(
        settings.planner_model
    ),

    researcher=ChatModelFactory.create(
        settings.researcher_model
    ),

    summariser=ChatModelFactory.create(
        settings.summariser_model
    ),

    reviewer=ChatModelFactory.create(
        settings.reviewer_model
    ),

    reporter=ChatModelFactory.create(
        settings.reporter_model
    ),

    controller=ChatModelFactory.create(
        settings.controller_model
    ),
)


#
# Research graph
#

graph = create_research_graph(
    models=agent_models,
    session_factory=SessionLocal,
    search_provider=search_provider,
    document_retriever=document_retriever,
    document_extractor=document_extractor,
)


#
# Workflow service
#

workflow_service = (
    ResearchWorkflowService(
        graph=graph,
        session_factory=SessionLocal,
    )
)


#
# Control service
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
)


print()
print(
    "CONTROL GENERATE REPORT TEST"
)
print(
    "============================"
)

print(
    f"Session: {SESSION_ID}"
)

print()


result = control_service.execute(
    user_message=(
        "Give me the research report."
    ),
    session_id=SESSION_ID,
)


print()
print(
    "CONTROL RESULT"
)
print(
    "=============="
)

print(
    result.model_dump_json(
        indent=2
    )
)


assert (
    result.operation
    == "generate_report"
)

assert (
    result.success is True
)

assert (
    result.report is not None
)

assert (
    result.report.report_id == 2
)

assert (
    result.report.session_id
    == SESSION_ID
)


print()
print(
    "PASS: Control Agent retrieved "
    "the existing research report."
)