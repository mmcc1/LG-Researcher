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

from persistence.search_attempt_repository import (
    SearchAttemptRepository,
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
    "REAL EVIDENCE-AWARE COUNTER-EVIDENCE "
    "WORKFLOW TEST"
)
print(
    "======================================"
)


session_id = (
    "fae69e3e-58d2-4c6a-8ac1-85cf6994db06"
)

question_id = 100

attempt_id = 16


#
# -------------------------------------------------
# Verify the prepared durable workflow state.
# -------------------------------------------------
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    attempt_repository = (
        SearchAttemptRepository(db)
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

    question = (
        session_repository.get_question(
            question_id
        )
    )

    attempt = (
        attempt_repository.get(
            attempt_id
        )
    )

    if research_session is None:
        raise ValueError(
            "Research session not found."
        )

    if question is None:
        raise ValueError(
            "Research question not found."
        )

    if attempt is None:
        raise ValueError(
            "Search attempt not found."
        )

    #
    # This test intentionally begins after
    # scheduling.
    #
    # Attempt 16 was created by the previous
    # evidence-context wiring test and has been
    # prepared for workflow continuation.
    #

    assert (
        research_session.status
        == "researching"
    )

    assert (
        question.status
        == "pending"
    )

    assert (
        attempt.research_session_id
        == session_id
    )

    assert (
        attempt.research_question_id
        == question_id
    )

    assert (
        attempt.purpose
        == "counter_evidence"
    )

    assert (
        attempt.status
        == "running"
    )

    sources_before = (
        source_repository.get_for_question(
            question_id
        )
    )

    findings_before = (
        finding_repository.get_for_question(
            question_id
        )
    )

    source_count_before = len(
        sources_before
    )

    finding_count_before = len(
        findings_before
    )

    question_text = question.question
    topic = research_session.topic


print()
print("BEFORE EVIDENCE-AWARE PASS")
print("--------------------------")

print(
    f"Session ID: {session_id}"
)

print(
    f"Session status: researching"
)

print(
    f"Question ID: {question_id}"
)

print(
    f"Question: {question_text}"
)

print(
    f"Question status: pending"
)

print(
    f"Attempt ID: {attempt_id}"
)

print(
    f"Attempt purpose: "
    f"{attempt.purpose}"
)

print(
    f"Attempt status: running"
)

print(
    f"Sources: {source_count_before}"
)

print(
    f"Findings: {finding_count_before}"
)


#
# -------------------------------------------------
# Production graph dependencies.
# -------------------------------------------------
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
# -------------------------------------------------
# Resume only the research phase.
#
# The graph should discover the already-running
# counter-evidence attempt rather than create a
# new attempt.
# -------------------------------------------------
#

print()
print(
    "Running evidence-aware "
    "counter-evidence research..."
)
print()


workflow_service.resume_research(
    session_id=session_id
)


#
# -------------------------------------------------
# Verify durable result.
# -------------------------------------------------
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    attempt_repository = (
        SearchAttemptRepository(db)
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

    question = (
        session_repository.get_question(
            question_id
        )
    )

    attempt = (
        attempt_repository.get(
            attempt_id
        )
    )

    sources_after = (
        source_repository.get_for_question(
            question_id
        )
    )

    findings_after = (
        finding_repository.get_for_question(
            question_id
        )
    )

    source_count_after = len(
        sources_after
    )

    finding_count_after = len(
        findings_after
    )


print()
print(
    "AFTER EVIDENCE-AWARE PASS"
)
print(
    "-------------------------"
)

print(
    f"Session status: "
    f"{research_session.status}"
)

print(
    f"Question status: "
    f"{question.status}"
)

print(
    f"Attempt status: "
    f"{attempt.status}"
)

print(
    f"Sources before: "
    f"{source_count_before}"
)

print(
    f"Sources after: "
    f"{source_count_after}"
)

print(
    f"Sources added: "
    f"{source_count_after - source_count_before}"
)

print(
    f"Findings before: "
    f"{finding_count_before}"
)

print(
    f"Findings after: "
    f"{finding_count_after}"
)

print(
    f"Findings added: "
    f"{finding_count_after - finding_count_before}"
)


#
# -------------------------------------------------
# Durable workflow assertions.
# -------------------------------------------------
#

assert (
    research_session.status
    == "researched"
)

assert (
    question.status
    == "researched"
)

assert (
    attempt.status
    == "completed"
)

assert (
    source_count_after
    >= source_count_before
)

assert (
    finding_count_after
    >= finding_count_before
)


#
# -------------------------------------------------
# Verify that the workflow did not create another
# active counter-evidence attempt for this question.
# -------------------------------------------------
#

with SessionLocal() as db:

    attempt_repository = (
        SearchAttemptRepository(db)
    )

    active_attempt = (
        attempt_repository
        .get_active_for_question(
            question_id
        )
    )


assert active_attempt is None


print()
print(
    "======================================"
)
print("PASS")
print(
    "======================================"
)

print(
    "Evidence-aware counter-evidence "
    "completed as an additive research pass."
)