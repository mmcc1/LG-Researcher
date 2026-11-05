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

from control.help_command_handler import (
    HelpCommandHandler,
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
# Research workflow service
#

workflow_service = (
    ResearchWorkflowService(
        graph=graph,
        session_factory=SessionLocal,
    )
)


#
# Control Agent
#

control_agent = ControlAgent(
    model=agent_models.controller,
)


#
# Control Service
#

control_service = ControlService(

    control_agent=control_agent,

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
)


#
# End-to-end test
#

print()
print(
    "STARTING CONTROL SERVICE "
    "END-TO-END TEST"
)
print(
    "========================="
)

print()

user_message = (
    "Start new research into: "
    "What cryptographic hash function does "
    "Bitcoin use for proof-of-work?"
)

print(
    "USER MESSAGE"
)
print(
    "------------"
)
print(
    user_message
)

print()
print(
    "Invoking ControlService..."
)
print()


try:

    result = (
        control_service.execute(
            user_message=user_message,
            session_id=None,
        )
    )

except Exception as ex:

    print()
    print(
        "CONTROL SERVICE FAILED"
    )
    print(
        "======================"
    )

    print(
        f"{type(ex).__name__}: {ex}"
    )

    raise


print()
print(
    "CONTROL SERVICE RESULT"
)
print(
    "======================"
)

print(
    result.model_dump_json(
        indent=2
    )
)