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

from persistence.review_repository import (
    ReviewRepository,
)

from persistence.report_repository import (
    ReportRepository,
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


SESSION_ID = (
    "fae69e3e-58d2-4c6a-8ac1-85cf6994db06"
)

FAILED_QUESTION_ID = 100


print()
print(
    "REAL REVIEW / REPORT RECOVERY TEST"
)
print(
    "=================================="
)


#
# -------------------------------------------------
# Verify the genuine interrupted state.
# -------------------------------------------------
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    review_repository = (
        ReviewRepository(db)
    )

    report_repository = (
        ReportRepository(db)
    )

    research_session = (
        session_repository.get(
            SESSION_ID
        )
    )

    if research_session is None:
        raise ValueError(
            "Research session not found."
        )

    questions = (
        session_repository.get_questions(
            SESSION_ID
        )
    )

    failed_question = (
        session_repository.get_question(
            FAILED_QUESTION_ID
        )
    )

    if failed_question is None:
        raise ValueError(
            "Failed research question "
            "not found."
        )

    failed_review_exists = (
        review_repository
        .exists_for_question(
            FAILED_QUESTION_ID
        )
    )

    report_exists = (
        report_repository
        .exists_for_session(
            SESSION_ID
        )
    )


#
# This test deliberately starts from the durable
# state left by the previous failed Review Agent
# invocation.
#

assert (
    research_session.status
    == "reviewing"
)

assert (
    failed_question.status
    == "reviewing"
)

assert (
    failed_review_exists
    is False
)

assert (
    report_exists
    is False
)


print()
print("BEFORE RECOVERY")
print("---------------")

print(
    f"Session ID: {SESSION_ID}"
)

print(
    f"Session status: "
    f"{research_session.status}"
)

print(
    f"Failed question: "
    f"{FAILED_QUESTION_ID}"
)

print(
    f"Failed question status: "
    f"{failed_question.status}"
)

print(
    f"Failed question review exists: "
    f"{failed_review_exists}"
)

print(
    f"Report exists: "
    f"{report_exists}"
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
# Resume from the genuine interrupted state.
#
# No database state is repaired manually.
# The production resume routing must recover the
# workflow from:
#
#     session = reviewing
#     Q100    = reviewing
#     review  = absent
#
# -------------------------------------------------
#

print()
print(
    "Resuming interrupted production "
    "workflow..."
)
print()


workflow_service.resume(
    session_id=SESSION_ID
)


#
# -------------------------------------------------
# Verify final durable state.
# -------------------------------------------------
#

with SessionLocal() as db:

    session_repository = (
        ResearchSessionRepository(db)
    )

    review_repository = (
        ReviewRepository(db)
    )

    report_repository = (
        ReportRepository(db)
    )

    research_session = (
        session_repository.get(
            SESSION_ID
        )
    )

    questions = (
        session_repository.get_questions(
            SESSION_ID
        )
    )

    reviews = (
        review_repository.get_for_session(
            SESSION_ID
        )
    )

    report = (
        report_repository.get_for_session(
            SESSION_ID
        )
    )


print()
print("AFTER RECOVERY")
print("--------------")

print(
    f"Session status: "
    f"{research_session.status}"
)

print(
    f"Questions: "
    f"{len(questions)}"
)

print(
    f"Reviews: "
    f"{len(reviews)}"
)

print(
    f"Report exists: "
    f"{report is not None}"
)


print()
print("QUESTION STATES")
print("---------------")


for question in questions:

    print(
        f"Question {question.id}: "
        f"{question.status}"
    )


if report is not None:

    print()
    print("REPORT")
    print("------")

    print(
        f"Report ID: "
        f"{report.id}"
    )

    print(
        f"Report title: "
        f"{report.title}"
    )

    print(
        f"Report sections: "
        f"{len(report.sections)}"
    )

    print(
        f"Report limitations: "
        f"{len(report.limitations)}"
    )


#
# -------------------------------------------------
# Final assertions.
# -------------------------------------------------
#

assert (
    research_session.status
    == "completed"
)

assert all(
    question.status == "reviewed"
    for question in questions
)

assert (
    len(reviews)
    == len(questions)
)

assert (
    report is not None
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
    "Interrupted review recovered and "
    "the complete review/report workflow "
    "finished successfully."
)