
from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from sqlalchemy.orm import sessionmaker

from application.guarded_graph_node import (
    GuardedGraphNode,
)

from agents.research_planner import (
    ResearchPlanner,
)

from agents.report_agent import (
    ReportAgent,
)

from agents.review_agent import (
    ReviewAgent,
)

from agents.search_planner import (
    SearchPlanner,
)

from agents.source_summariser import (
    SourceSummariser,
)

from extraction.html import (
    HtmlDocumentExtractor,
)

from graph.state import ResearchState

from models.agent_models import (
    AgentModels,
)

from nodes.analyse_sources import (
    AnalyseSourcesNode,
)

from nodes.check_existing_search import (
    CheckExistingSearchNode,
)

from nodes.complete_question import (
    CompleteQuestionNode,
)

from nodes.complete_report import (
    CompleteReportNode,
)

from nodes.complete_research import (
    CompleteResearchNode,
)

from nodes.complete_review import (
    CompleteReviewNode,
)

from nodes.create_search_plan import (
    CreateSearchPlanNode,
)

from nodes.generate_report import (
    GenerateReportNode,
)

from nodes.retrieve_sources import (
    RetrieveSourcesNode,
)

from nodes.review_question import (
    ReviewQuestionNode,
)

from nodes.save_research_plan import (
    SaveResearchPlanNode,
)

from nodes.save_search_results import (
    SaveSearchResultsNode,
)

from nodes.search_web import (
    SearchWebNode,
)

from nodes.select_question import (
    SelectQuestionNode,
)

from nodes.select_resume_phase import (
    SelectResumePhaseNode,
)

from nodes.select_review_question import (
    SelectReviewQuestionNode,
)

from processing.chunk_ranker import (
    QuestionChunkRanker,
)

from processing.report_context_builder import (
    ReportContextBuilder,
)

from processing.report_validator import (
    ReportValidator,
)

from processing.review_context_builder import (
    ReviewContextBuilder,
)

from processing.source_context_builder import (
    SourceContextBuilder,
)

from processing.text_chunker import (
    TextChunker,
)

from retrieval.base import (
    DocumentRetriever,
)

from search.base import (
    SearchProvider,
)

from nodes.check_pause import (
    CheckPauseNode,
)


def route_pause(
    state: ResearchState,
) -> str:

    if state.get(
        "pause_requested",
        False,
    ):

        return "pause"

    return "continue"


def create_research_graph(
    models: AgentModels,
    session_factory: sessionmaker,
    search_provider: SearchProvider,
    document_retriever: DocumentRetriever,
    document_extractor: HtmlDocumentExtractor,
):

    #
    # -------------------------------------------------
    # Research phase dependencies
    # -------------------------------------------------
    #

    complete_question = (
        CompleteQuestionNode(
            session_factory=session_factory,
        )
    )

    text_chunker = TextChunker(
        chunk_size=4000,
        overlap=400,
    )

    chunk_ranker = (
        QuestionChunkRanker()
    )

    source_context_builder = (
        SourceContextBuilder(
            chunker=text_chunker,
            ranker=chunk_ranker,
            max_chunks=3,
            max_characters=10000,
        )
    )

    retrieve_sources = (
        RetrieveSourcesNode(
            session_factory=(
                session_factory
            ),
            retriever=(
                document_retriever
            ),
            extractor=(
                document_extractor
            ),
            max_sources=5,
        )
    )

    source_summariser = (
        SourceSummariser(
            model=models.summariser
        )
    )

    analyse_sources = (
        AnalyseSourcesNode(
            session_factory=(
                session_factory
            ),
            summariser=(
                source_summariser
            ),
            context_builder=(
                source_context_builder
            ),
        )
    )

    research_planner = (
        ResearchPlanner(
            model=models.planner
        )
    )

    save_research_plan = (
        SaveResearchPlanNode(
            session_factory=(
                session_factory
            ),
        )
    )

    check_existing_search = (
        CheckExistingSearchNode(
            session_factory=session_factory,
        )
    )

    search_planner = (
        SearchPlanner(
            model=models.researcher
        )
    )

    select_question = (
        SelectQuestionNode(
            session_factory=(
                session_factory
            )
        )
    )

    create_search_plan = (
        CreateSearchPlanNode(
            search_planner=(
                search_planner
            ),
            session_factory=session_factory,
        )
    )

    search_web = (
        SearchWebNode(
            search_provider=(
                search_provider
            ),
            results_per_query=5,
        )
    )

    save_search_results = (
        SaveSearchResultsNode(
            session_factory=(
                session_factory
            )
        )
    )

    complete_research = (
        CompleteResearchNode(
            session_factory=(
                session_factory
            ),
        )
    )

    #
    # -------------------------------------------------
    # Review phase dependencies
    # -------------------------------------------------
    #

    review_agent = (
        ReviewAgent(
            model=models.reviewer
        )
    )

    review_context_builder = (
        ReviewContextBuilder()
    )

    select_review_question = (
        SelectReviewQuestionNode(
            session_factory=(
                session_factory
            )
        )
    )

    review_question = (
        ReviewQuestionNode(
            session_factory=(
                session_factory
            ),
            review_agent=(
                review_agent
            ),
            context_builder=(
                review_context_builder
            ),
        )
    )

    complete_review = (
        CompleteReviewNode(
            session_factory=(
                session_factory
            )
        )
    )

    #
    # -------------------------------------------------
    # Report phase dependencies
    # -------------------------------------------------
    #

    report_agent = (
        ReportAgent(
            model=models.reporter
        )
    )

    report_context_builder = (
        ReportContextBuilder()
    )

    report_validator = (
        ReportValidator()
    )

    generate_report = (
        GenerateReportNode(
            session_factory=(
                session_factory
            ),
            report_agent=(
                report_agent
            ),
            context_builder=(
                report_context_builder
            ),
            validator=(
                report_validator
            ),
        )
    )

    complete_report = (
        CompleteReportNode(
            session_factory=(
                session_factory
            )
        )
    )

    #
    # -------------------------------------------------
    # Resume dependencies
    # -------------------------------------------------
    #

    select_resume_phase = (
        SelectResumePhaseNode(
            session_factory=(
                session_factory
            )
        )
    )

    #
    # -------------------------------------------------
    # Cooperative pause dependency
    # -------------------------------------------------
    #

    check_pause = (
        CheckPauseNode(
            session_factory=(
                session_factory
            )
        )
    )

    #
    # -------------------------------------------------
    # Graph
    # -------------------------------------------------
    #

    builder = StateGraph(
        ResearchState
    )

    #
    # Nodes
    #

    builder.add_node(
        "plan_research",
        GuardedGraphNode(
            node=research_planner,
        ),
    )

    builder.add_node(
        "save_research_plan",
        GuardedGraphNode(
            node=save_research_plan,
        ),
    )

    builder.add_node(
        "select_question",
        GuardedGraphNode(
            node=select_question,
        ),
    )

    builder.add_node(
        "check_existing_search",
        GuardedGraphNode(
            node=check_existing_search,
        ),
    )

    builder.add_node(
        "create_search_plan",
        GuardedGraphNode(
            node=create_search_plan,
        ),
    )

    builder.add_node(
        "search_web",
        GuardedGraphNode(
            node=search_web,
        ),
    )

    builder.add_node(
        "save_search_results",
        GuardedGraphNode(
            node=save_search_results,
        ),
    )

    builder.add_node(
        "retrieve_sources",
        GuardedGraphNode(
            node=retrieve_sources,
        ),
    )

    builder.add_node(
        "analyse_sources",
        GuardedGraphNode(
            node=analyse_sources,
        ),
    )

    builder.add_node(
        "complete_question",
        GuardedGraphNode(
            node=complete_question,
        ),
    )

    builder.add_node(
        "complete_research",
        GuardedGraphNode(
            node=complete_research,
        ),
    )

    builder.add_node(
        "select_review_question",
        GuardedGraphNode(
            node=select_review_question,
        ),
    )

    builder.add_node(
        "review_question",
        GuardedGraphNode(
            node=review_question,
        ),
    )

    builder.add_node(
        "complete_review",
        GuardedGraphNode(
            node=complete_review,
        ),
    )

    builder.add_node(
        "generate_report",
        GuardedGraphNode(
            node=generate_report,
        ),
    )

    builder.add_node(
        "complete_report",
        GuardedGraphNode(
            node=complete_report,
        ),
    )

    builder.add_node(
        "select_resume_phase",
        GuardedGraphNode(
            node=select_resume_phase,
        ),
    )

    #
    # Cooperative pause nodes.
    #
    # These all use the same CheckPauseNode
    # implementation. Separate graph node names
    # allow each safe boundary to have its own
    # continuation destination.
    #

    builder.add_node(
        "check_pause_planning",
        GuardedGraphNode(
            node=check_pause,
        ),
    )

    builder.add_node(
        "check_pause_research",
        GuardedGraphNode(
            node=check_pause,
        ),
    )

    builder.add_node(
        "check_pause_after_research",
        GuardedGraphNode(
            node=check_pause,
        ),
    )

    builder.add_node(
        "check_pause_review",
        GuardedGraphNode(
            node=check_pause,
        ),
    )

    builder.add_node(
        "check_pause_after_review",
        GuardedGraphNode(
            node=check_pause,
        ),
    )

    builder.add_node(
        "check_pause_report",
        GuardedGraphNode(
            node=check_pause,
        ),
    )

    builder.add_node(
        "check_pause_before_report",
        GuardedGraphNode(
            node=check_pause,
        ),
    )

    #
    # -------------------------------------------------
    # Start routing
    # -------------------------------------------------
    #

    builder.add_conditional_edges(
        START,
        route_start,
        {
            "new": "plan_research",
            "resume": "select_resume_phase",
        },
    )

    builder.add_conditional_edges(
        "select_resume_phase",
        route_resume_phase,
        {
            "planning": "plan_research",
            "research": "select_question",
            "review": "select_review_question",
            "report": "check_pause_before_report",
            "finished": END,
        },
    )

    #
    # -------------------------------------------------
    # Research phase
    # -------------------------------------------------
    #

    builder.add_edge(
        "plan_research",
        "save_research_plan",
    )

    #
    # The research plan has now been durably saved.
    #
    # Honour a cooperative pause before beginning
    # question research.
    #

    builder.add_edge(
        "save_research_plan",
        "check_pause_planning",
    )

    builder.add_conditional_edges(
        "check_pause_planning",
        route_pause,
        {
            "pause": END,
            "continue": "select_question",
        },
    )

    #
    # Selecting a question does not immediately
    # generate a new search plan.
    #
    # First determine whether this question already
    # has durable search results. This is important
    # when recovering an interrupted research run.
    #

    builder.add_conditional_edges(
        "select_question",
        route_after_question_selection,
        {
            "research": (
                "check_existing_search"
            ),
            "finished": (
                "complete_research"
            ),
        },
    )

    #
    # If search results already exist for the
    # question, reuse those persisted results and
    # continue directly to source retrieval.
    #
    # Otherwise perform the normal search-planning
    # and search path.
    #

    builder.add_conditional_edges(
        "check_existing_search",
        route_search,
        {
            "search": (
                "create_search_plan"
            ),
            "reuse": (
                "retrieve_sources"
            ),
        },
    )

    builder.add_edge(
        "create_search_plan",
        "search_web",
    )

    builder.add_edge(
        "search_web",
        "save_search_results",
    )

    builder.add_edge(
        "save_search_results",
        "retrieve_sources",
    )

    builder.add_edge(
        "retrieve_sources",
        "analyse_sources",
    )

    builder.add_edge(
        "analyse_sources",
        "complete_question",
    )

    #
    # One complete research-question unit has
    # finished and its durable state has been
    # updated.
    #
    # Check for a pause before selecting and
    # beginning another question.
    #

    builder.add_edge(
        "complete_question",
        "check_pause_research",
    )

    builder.add_conditional_edges(
        "check_pause_research",
        route_pause,
        {
            "pause": END,
            "continue": "select_question",
        },
    )

    #
    # -------------------------------------------------
    # Transition from research to review
    # -------------------------------------------------
    #
    # Research-only execution still terminates
    # immediately after CompleteResearchNode.
    #
    # Full execution passes through another pause
    # boundary before review begins. This catches a
    # pause request arriving while the durable
    # research-completion transition is occurring.
    #

    builder.add_conditional_edges(
        "complete_research",
        route_after_research_completion,
        {
            "stop": END,
            "review": (
                "check_pause_after_research"
            ),
        },
    )

    builder.add_conditional_edges(
        "check_pause_after_research",
        route_pause,
        {
            "pause": END,
            "continue": (
                "select_review_question"
            ),
        },
    )

    #
    # -------------------------------------------------
    # Review phase
    # -------------------------------------------------
    #

    builder.add_conditional_edges(
        "select_review_question",
        route_after_review_selection,
        {
            "review": "review_question",
            "finished": "complete_review",
        },
    )

    #
    # One complete review unit has finished and
    # its durable review has been persisted.
    #
    # Check for a pause before selecting another
    # review question.
    #

    builder.add_edge(
        "review_question",
        "check_pause_review",
    )

    builder.add_conditional_edges(
        "check_pause_review",
        route_pause,
        {
            "pause": END,
            "continue": (
                "select_review_question"
            ),
        },
    )

    #
    # -------------------------------------------------
    # Transition from review to reporting
    # -------------------------------------------------
    #
    # CompleteReviewNode performs the durable
    # lifecycle transition to reviewed.
    #
    # Honour a pause request before beginning the
    # potentially expensive report-generation step.
    #

    builder.add_conditional_edges(
        "complete_review",
        route_after_review_completion,
        {
            "stop": END,
            "report": "check_pause_after_review",
        },
    )

    builder.add_conditional_edges(
        "check_pause_after_review",
        route_pause,
        {
            "pause": END,
            "continue": "generate_report",
        },
    )

    #
    # -------------------------------------------------
    # Report phase
    # -------------------------------------------------
    #

    #
    # When resuming a session in the reporting phase,
    # check for a pause request before generating
    # the report.
    #
    # This protects against a pause request arriving
    # after the recovery controller has validated
    # eligibility but before the graph begins
    # executing the Report Agent.
    #

    builder.add_conditional_edges(
        "check_pause_before_report",
        route_pause,
        {
            "pause": END,
            "continue": "generate_report",
        },
    )

    #
    # GenerateReportNode may perform a long-running
    # model call and persist the report.
    #
    # Once that logical unit has completed, check
    # for a pause before marking the overall
    # research session completed.
    #

    builder.add_edge(
        "generate_report",
        "check_pause_report",
    )

    builder.add_conditional_edges(
        "check_pause_report",
        route_pause,
        {
            "pause": END,
            "continue": "complete_report",
        },
    )

    builder.add_edge(
        "complete_report",
        END,
    )

    return builder.compile()


def route_after_question_selection(
    state: ResearchState,
) -> str:

    if (
        state[
            "current_question_id"
        ]
        is None
    ):

        return "finished"

    return "research"


def route_search(
    state: ResearchState,
) -> str:

    if state.get(
        "search_required",
        True,
    ):

        return "search"

    return "reuse"


def route_after_review_selection(
    state: ResearchState,
) -> str:

    if (
        state[
            "current_review_question_id"
        ]
        is None
    ):

        return "finished"

    return "review"


def route_start(
    state: ResearchState,
) -> str:

    if state.get(
        "resume",
        False,
    ):

        return "resume"

    return "new"


def route_resume_phase(
    state: ResearchState,
) -> str:

    status = state.get(
        "resume_phase"
    )

    execution_target = state.get(
        "execution_target",
        "complete",
    )

    #
    # Validate the requested execution target.
    #

    if execution_target not in {
        "research",
        "review",
        "complete",
    }:

        raise ValueError(
            "Unknown research graph "
            "execution target: "
            f"{execution_target}"
        )

    #
    # Research-only execution.
    #
    # Resume planning or research when needed.
    # Stop if research has already completed.
    #

    if execution_target == "research":

        if status in {
            "created",
            "planning",
        }:

            return "planning"

        if status in {
            "planned",
            "researching",
        }:

            return "research"

        if status in {
            "researched",
            "reviewing",
            "reviewed",
            "reporting",
            "completed",
        }:

            return "finished"

    #
    # Review-only execution.
    #
    # A review-only run requires completed
    # research. It must not restart research
    # or continue into report generation.
    #

    if execution_target == "review":

        if status in {
            "researched",
            "reviewing",
        }:

            return "review"

        if status in {
            "reviewed",
            "reporting",
            "completed",
        }:

            return "finished"

        raise ValueError(
            "Cannot execute review phase "
            "before research is completed. "
            f"Current session status: {status}"
        )

    #
    # Complete execution.
    #
    # Resume whichever phase is appropriate
    # for the persisted session status.
    #

    if execution_target == "complete":

        if status in {
            "created",
            "planning",
        }:

            return "planning"

        if status in {
            "planned",
            "researching",
        }:

            return "research"

        if status in {
            "researched",
            "reviewing",
        }:

            return "review"

        if status in {
            "reviewed",
            "reporting",
        }:

            return "report"

        if status == "completed":

            return "finished"

    raise ValueError(
        "Cannot determine resume "
        "phase from research session "
        f"status: {status}"
    )


def route_after_research_completion(
    state: ResearchState,
) -> str:

    execution_target = state.get(
        "execution_target",
        "complete",
    )

    if execution_target == "research":

        return "stop"

    if execution_target == "complete":

        return "review"

    raise ValueError(
        "Unknown research graph "
        "execution target: "
        f"{execution_target}"
    )


def route_after_review_completion(
    state: ResearchState,
) -> str:

    execution_target = state.get(
        "execution_target",
        "complete",
    )

    if execution_target == "review":

        return "stop"

    if execution_target == "complete":

        return "report"

    raise ValueError(
        "Unknown execution target: "
        f"{execution_target}"
    )
