#     LGResearcher - A Langgraph-based LLM agnostic research engine
#     Copyright (C) 2026  Mark McCarron

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>

import logging
import time

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

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from application.research_job_worker import (
    ResearchJobWorker,
)


logger = logging.getLogger(__name__)


def create_workflow_service():

    url_validator = UrlValidator()

    document_retriever = HttpDocumentRetriever(
        url_validator=url_validator,
    )

    document_extractor = HtmlDocumentExtractor()

    search_provider = DuckDuckGoSearchProvider()

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

    workflow_service = ResearchWorkflowService(
        graph=graph,
        session_factory=SessionLocal,
    )

    return workflow_service


def main():

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s: "
            "%(message)s"
        ),
    )

    poll_interval_seconds = 5.0

    logger.info(
        "Starting LG Researcher worker."
    )

    workflow_service = create_workflow_service()

    worker = ResearchJobWorker(
        session_factory=SessionLocal,
        workflow_service=workflow_service,
        lease_duration_seconds=120,
        heartbeat_interval_seconds=30.0,
    )

    logger.info(
        "Worker initialized. "
        "Polling every %.1f seconds.",
        poll_interval_seconds,
    )

    try:

        while True:

            try:

                job_id = worker.process_next()

                if job_id is None:

                    logger.debug(
                        "No research jobs available."
                    )

                    time.sleep(
                        poll_interval_seconds
                    )

                    continue

                logger.info(
                    "Finished processing research job %s",
                    job_id,
                )

            except KeyboardInterrupt:

                raise

            except Exception:

                logger.exception(
                    "Research job processing failed."
                )

                time.sleep(
                    poll_interval_seconds
                )

    except KeyboardInterrupt:

        logger.info(
            "Worker shutdown requested."
        )

    finally:

        logger.info(
            "LG Researcher worker stopped."
        )


if __name__ == "__main__":
    main()
