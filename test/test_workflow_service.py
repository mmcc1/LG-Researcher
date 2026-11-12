from application.research_workflow_service import (
    ResearchWorkflowService,
)

from persistence.database import SessionLocal
from models.agent_models import AgentModels
from models.factory import ChatModelFactory
from config import settings
from graph.research_graph import create_research_graph
from search.duckduckgo import (
    DuckDuckGoSearchProvider,
)
from extraction.html import HtmlDocumentExtractor
from retrieval.http import HttpDocumentRetriever
from security.url_validator import UrlValidator

SESSION_ID = (
    "063bd913-9e9a-48bd-81d7-8738153a7863"
)

url_validator = UrlValidator()

document_retriever = HttpDocumentRetriever(
        url_validator=url_validator,
)

document_extractor = HtmlDocumentExtractor()

search_provider = (
    DuckDuckGoSearchProvider()
)


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

workflow_service = (
    ResearchWorkflowService(
        graph= create_research_graph(
        models=agent_models,
        session_factory=SessionLocal,
        search_provider=search_provider,
        document_retriever=document_retriever,
        document_extractor=document_extractor,
    ),
        session_factory=SessionLocal,
    )
)


try:

    workflow_service.resume(
        session_id=SESSION_ID
    )

except ValueError as error:

    print()
    print(
        "EXPECTED REJECTION"
    )
    print(
        "=================="
    )
    print(error)