from config import settings

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from extraction.html import (
    HtmlDocumentExtractor,
)

from graph.research_graph import (
    create_research_graph,
)

from models.agent_models import (
    AgentModels,
)

from models.factory import (
    ChatModelFactory,
)

from persistence.database import (
    SessionLocal,
)

from persistence.research_session_repository import (
    ResearchSessionRepository,
)

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
)

from persistence.search_repository import (
    SearchRepository,
)

from retrieval.http import (
    HttpDocumentRetriever,
)

from search.duckduckgo import (
    DuckDuckGoSearchProvider,
)

from security.url_validator import (
    UrlValidator,
)


SESSION_ID = (
    "8325d0ed-407a-43e9-8ba2-be861de668aa"
)

QUESTION_ID = 97

ATTEMPT_ID = 5


print()
print(
    "REAL DEEPER RESEARCH WORKFLOW TEST"
)
print(
    "=================================="
)


#
# Verify the durable test state before
# starting the real workflow.
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    attempt_repository = (
        SearchAttemptRepository(db)
    )

    research_session = (
        session_repository.get(
            SESSION_ID
        )
    )

    attempt = (
        attempt_repository.get(
            ATTEMPT_ID
        )
    )

    assert research_session is not None
    assert attempt is not None

    assert (
        attempt.research_session_id
        == SESSION_ID
    )

    assert (
        attempt.research_question_id
        == QUESTION_ID
    )

    assert (
        attempt.purpose
        == "deeper_research"
    )

    assert (
        attempt.status
        in {
            "pending",
            "running",
        }
    )

    print()
    print("PRE-RUN STATE")
    print("-------------")

    print(
        f"Session status: "
        f"{research_session.status}"
    )

    print(
        f"Attempt status: "
        f"{attempt.status}"
    )

    print(
        f"Attempt purpose: "
        f"{attempt.purpose}"
    )

    print(
        f"Instructions: "
        f"{attempt.instructions}"
    )


#
# Build exactly the same infrastructure
# used by app.py.
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
# Build exactly the same model registry
# used by app.py.
#

print()
print("Loading models...")

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
# Construct the real graph.
#

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
# Resume the real persisted workflow.
#

print()
print(
    f"Resuming session {SESSION_ID}..."
)
print()

workflow_result = (
    workflow_service.resume(
        session_id=SESSION_ID
    )
)


print()
print(
    "Workflow returned successfully."
)


#
# Verify durable SearchAttempt state.
#

with SessionLocal() as db:

    attempt_repository = (
        SearchAttemptRepository(db)
    )

    attempt = (
        attempt_repository.get(
            ATTEMPT_ID
        )
    )

    assert attempt is not None

    print()
    print("POST-RUN ATTEMPT")
    print("----------------")

    print(
        f"Attempt ID: "
        f"{attempt.id}"
    )

    print(
        f"Purpose: "
        f"{attempt.purpose}"
    )

    print(
        f"Status: "
        f"{attempt.status}"
    )

    assert (
        attempt.status
        == "completed"
    )


#
# Verify search-result provenance.
#

with SessionLocal() as db:

    search_repository = (
        SearchRepository(db)
    )

    results = (
        search_repository
        .get_results_for_attempt(
            ATTEMPT_ID
        )
    )

    print()
    print(
        "ATTEMPT SEARCH RESULTS"
    )
    print(
        "----------------------"
    )

    print(
        f"Result count: "
        f"{len(results)}"
    )

    assert len(results) > 0

    for result in results:

        assert (
            result.search_attempt_id
            == ATTEMPT_ID
        )

        assert (
            result.research_session_id
            == SESSION_ID
        )

        assert (
            result.research_question_id
            == QUESTION_ID
        )

        print()
        print(
            f"Result ID: "
            f"{result.id}"
        )

        print(
            f"Query: "
            f"{result.query}"
        )

        print(
            f"Rank: "
            f"{result.rank}"
        )

        print(
            f"Title: "
            f"{result.title}"
        )

        print(
            f"URL: "
            f"{result.url}"
        )


#
# Show final session/question state.
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    research_session = (
        session_repository.get(
            SESSION_ID
        )
    )

    question = (
        session_repository.get_question(
            QUESTION_ID
        )
    )

    assert research_session is not None
    assert question is not None

    print()
    print("FINAL WORKFLOW STATE")
    print("--------------------")

    print(
        f"Session status: "
        f"{research_session.status}"
    )

    print(
        f"Question status: "
        f"{question.status}"
    )


print()
print(
    "=================================="
)
print("PASS")
print(
    "=================================="
)
print(
    "The persisted deeper-research "
    "attempt was recovered and executed."
)
print(
    "Its search results retain explicit "
    "SearchAttempt provenance."
)