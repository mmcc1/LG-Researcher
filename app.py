from config import settings
from graph.research_graph import create_research_graph
from persistence.database import SessionLocal
from persistence.research_session_repository import (
    ResearchSessionRepository,
)
from models.agent_models import AgentModels
from models.factory import ChatModelFactory

from search.duckduckgo import (
    DuckDuckGoSearchProvider,
)
from extraction.html import HtmlDocumentExtractor
from retrieval.http import HttpDocumentRetriever
from security.url_validator import UrlValidator

from application.research_workflow_service import (
    ResearchWorkflowService,
)


def main():

    #
    # Infrastructure
    #

    url_validator = UrlValidator()

    document_retriever = HttpDocumentRetriever(
        url_validator=url_validator,
    )

    document_extractor = HtmlDocumentExtractor()

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
    # Graph
    #

    graph = create_research_graph(
        models=agent_models,
        session_factory=SessionLocal,
        search_provider=search_provider,
        document_retriever=document_retriever,
        document_extractor=document_extractor,
    )

    #
    # Reusable workflow service
    #

    workflow_service = (
        ResearchWorkflowService(
            graph=graph,
            session_factory=SessionLocal,
        )
    )

    #
    # Startup
    #

    print("Researcher")
    print("----------")
    print()
    print("1. Start new research")
    print("2. Resume research")
    print()

    choice = input(
        "Select: "
    ).strip()

    if choice == "1":

        topic = input(
            "Enter research topic: "
        ).strip()

        if not topic:

            print()
            print(
                "A research topic is required."
            )

            return

        print()
        print(
            f"Topic: {topic}"
        )

        print()

        print(
            "Invoking research graph...",
            flush=True,
        )

        try:

            workflow_result = (
                workflow_service.start(
                    topic=topic
                )
            )

            result = (
                workflow_result.graph_result
            )

        except Exception as ex:

            print()
            print(
                "Research workflow failed:"
            )

            print(
                f"{type(ex).__name__}: {ex}"
            )

            return

    elif choice == "2":

        research_session = (
            select_existing_research_session()
        )

        if research_session is None:
            return

        print()
        print(
            f"Research session: "
            f"{research_session.id}"
        )

        print(
            f"Topic: "
            f"{research_session.topic}"
        )

        print(
            f"Status: "
            f"{research_session.status}"
        )

        print()

        print(
            "Resuming research graph...",
            flush=True,
        )

        try:

            workflow_result = (
                workflow_service.resume(
                    session_id=(
                        research_session.id
                    )
                )
            )

            result = (
                workflow_result.graph_result
            )

        except Exception as ex:

            print()
            print(
                "Research workflow failed:"
            )

            print(
                f"{type(ex).__name__}: {ex}"
            )

            return

    else:

        print()
        print("Invalid selection.")
        return

    print()
    print(
        "Research graph completed."
    )

    #
    # Diagnostics
    #

    display_diagnostics(
        result
    )


def select_existing_research_session():

    print()

    session_id = input(
        "Enter research session ID: "
    ).strip()

    if not session_id:

        print(
            "A research session ID "
            "is required."
        )

        return None

    with SessionLocal() as db:

        repository = (
            ResearchSessionRepository(db)
        )

        research_session = (
            repository.get(
                session_id
            )
        )

    if research_session is None:

        print()
        print(
            "Research session not found."
        )

        return None

    #
    # "completed" is the only terminal
    # workflow state.
    #

    if (
        research_session.status
        == "completed"
    ):

        print()
        print(
            "This research session has "
            "already been completed."
        )

        return None

    return research_session


def display_diagnostics(
    result,
):

    #
    # Selected question
    #

    current_question = result.get(
        "current_question"
    )

    if current_question is not None:

        print()
        print("SELECTED QUESTION")
        print("-----------------")
        print(current_question)

    #
    # Search plan
    #

    search_plan = result.get(
        "search_plan"
    )

    if search_plan is not None:

        print()
        print("SEARCH PLAN")
        print("-----------")

        for query in search_plan.queries:

            print()
            print(query.query)

            print(
                f"Why: "
                f"{query.rationale}"
            )

    #
    # Search results
    #

    search_results = result.get(
        "search_results",
        [],
    )

    if search_results:

        print()
        print("SEARCH RESULTS")
        print("--------------")

        for search_result in search_results:

            print()
            print(
                search_result.title
            )
            print(
                search_result.url
            )
            print(
                search_result.snippet
            )

    #
    # Research plan
    #

    plan = result.get(
        "research_plan"
    )

    if plan is not None:

        print()
        print("RESEARCH PLAN")
        print("-------------")

        print()
        print(plan.topic)

        for index, question in enumerate(
            plan.questions,
            start=1,
        ):

            print()

            print(
                f"{index}. "
                f"[{question.category}]"
            )

            print(
                question.question
            )

            print(
                f"   Why: "
                f"{question.rationale}"
            )


if __name__ == "__main__":
    main()