from config import settings

from graph.research_graph import (
    create_research_graph,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.source_repository import (
    SourceRepository,
)

from persistence.finding_repository import (
    FindingRepository,
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

from application.research_workflow_service import (
    ResearchWorkflowService,
)


print()
print(
    "REAL RESEARCH-ONLY WORKFLOW TEST"
)
print(
    "================================"
)


#
# Production dependencies.
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


graph = create_research_graph(
    models=agent_models,
    session_factory=SessionLocal,
    search_provider=search_provider,
    document_retriever=document_retriever,
    document_extractor=document_extractor,
)


workflow_service = (
    ResearchWorkflowService(
        graph=graph,
        session_factory=SessionLocal,
    )
)


#
# Keep the topic deliberately focused.
#
# We want genuine evidence suitable for the
# subsequent counter-evidence test without
# creating an unnecessarily large research run.
#

topic = (
    "What role does SHA-256 play "
    "in Bitcoin proof-of-work?"
)


print()
print("TOPIC")
print("-----")
print(topic)

print()
print(
    "Starting research-only workflow..."
)
print()


result = workflow_service.start_research(
    topic=topic
)


session_id = result.session_id


print()
print(
    "GRAPH RETURNED"
)
print(
    "--------------"
)

print(
    f"Session ID: {session_id}"
)


#
# Inspect durable state.
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    source_repository = (
        SourceRepository(db)
    )

    finding_repository = (
        FindingRepository(db)
    )

    research_session = (
        session_repository.get(
            session_id
        )
    )

    questions = (
        session_repository.get_questions(
            session_id
        )
    )

    print()
    print(
        "PERSISTED SESSION"
    )
    print(
        "-----------------"
    )

    print(
        f"Status: "
        f"{research_session.status}"
    )

    assert (
        research_session.status
        == "researched"
    )


    print()
    print(
        "QUESTIONS"
    )
    print(
        "---------"
    )

    for question in questions:

        print()
        print(
            f"Question ID: "
            f"{question.id}"
        )

        print(
            f"Status: "
            f"{question.status}"
        )

        print(
            f"Question: "
            f"{question.question}"
        )

        assert (
            question.status
            == "researched"
        )

        sources = (
            source_repository
            .get_for_question(
                question.id
            )
        )

        findings = (
            finding_repository
            .get_for_question(
                question.id
            )
        )

        print(
            f"Sources: "
            f"{len(sources)}"
        )

        print(
            f"Findings: "
            f"{len(findings)}"
        )

        assert len(sources) > 0
        assert len(findings) > 0


print()
print(
    "================================"
)
print("PASS")
print(
    "================================"
)
print(
    "Research stopped at the durable "
    "'researched' boundary."
)
print(
    f"Candidate session: {session_id}"
)