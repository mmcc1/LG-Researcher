
"""
Standalone operational recovery worker.

Commands:

    python recovery_worker.py --once --limit 25

    python recovery_worker.py --once --session-id UUID

    python recovery_worker.py --continuous --interval 30 --limit 25

    python recovery_worker.py --continuous --interval 30 --limit 25 \
        --health-file runtime/recovery-health.json

Exit codes:

    0 - Completed normally
    1 - One or more recovery sessions failed (single cycle)
    2 - Initialization or coordinator failure
    3 - Targeted recovery skipped
"""

import argparse
import logging
import math
import signal
import sys
import time

from contextlib import nullcontext

from config import settings

from graph.research_graph import create_research_graph
from persistence.database import SessionLocal

from models.agent_models import AgentModels
from models.factory import ChatModelFactory

from search.duckduckgo import DuckDuckGoSearchProvider
from extraction.html import HtmlDocumentExtractor
from retrieval.http import HttpDocumentRetriever
from security.url_validator import UrlValidator

from application.research_workflow_service import (
    ResearchWorkflowService,
)

from application.research_recovery_service import (
    ResearchRecoveryService,
)

from application.research_recovery_worker import (
    ResearchRecoveryWorker,
)

from application.research_recovery_scheduler import (
    ResearchRecoveryScheduler,
)

from application.research_recovery_monitor import (
    RecoveryHealthMonitor,
    JsonLogFormatter,
)

from application.recovery_health_ownership import (
    RecoveryHealthOwnership,
)


logger = logging.getLogger("research.recovery")


# ------------------------------------------------------------
# Argument validation
# ------------------------------------------------------------

def positive_batch_limit(value):

    try:
        limit = int(value)

    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            "Batch limit must be an integer."
        )

    if not 1 <= limit <= 1000:
        raise argparse.ArgumentTypeError(
            "Batch limit must be between 1 and 1000."
        )

    return limit


def positive_interval(value):

    try:
        interval = float(value)

    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            "Polling interval must be numeric."
        )

    if (
        not math.isfinite(interval)
        or not 0.1 <= interval <= 86400
    ):
        raise argparse.ArgumentTypeError(
            "Polling interval must be between "
            "0.1 and 86400 seconds."
        )

    return interval


# ------------------------------------------------------------
# Command-line arguments
# ------------------------------------------------------------

def parse_arguments(argv=None):

    parser = argparse.ArgumentParser(
        description="Recover abandoned research sessions."
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--once",
        action="store_true",
        help="Run one recovery cycle and exit.",
    )

    mode.add_argument(
        "--continuous",
        action="store_true",
        help="Run periodic recovery until stopped.",
    )

    selection = parser.add_mutually_exclusive_group()

    selection.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Recover one specific eligible session.",
    )

    selection.add_argument(
        "--limit",
        type=positive_batch_limit,
        default=None,
        help="Maximum batch size (default: 25).",
    )

    parser.add_argument(
        "--interval",
        type=positive_interval,
        default=None,
        help=(
            "Seconds between completed cycles "
            "(default: 30)."
        ),
    )

    parser.add_argument(
        "--health-file",
        type=str,
        default=None,
        help=(
            "Write an atomic JSON health snapshot "
            "during continuous operation."
        ),
    )

    args = parser.parse_args(argv)

    if args.health_file is not None:

        if not args.continuous:
            parser.error(
                "--health-file requires --continuous."
            )

        if not args.health_file.strip():
            parser.error(
                "--health-file cannot be empty."
            )

        args.health_file = args.health_file.strip()

    if args.session_id is not None:

        args.session_id = args.session_id.strip()

        if not args.session_id:
            parser.error(
                "--session-id cannot be empty."
            )

        if args.continuous:
            parser.error(
                "--session-id cannot be used "
                "with --continuous."
            )

    if args.interval is not None and args.once:
        parser.error(
            "--interval requires --continuous."
        )

    if args.limit is None:
        args.limit = 25

    if args.interval is None:
        args.interval = 30.0

    return args


# ------------------------------------------------------------
# Production dependency construction
# ------------------------------------------------------------

def create_production_worker():

    # Infrastructure

    url_validator = UrlValidator()

    document_retriever = HttpDocumentRetriever(
        url_validator=url_validator,
    )

    document_extractor = HtmlDocumentExtractor()

    search_provider = DuckDuckGoSearchProvider()

    # Models

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

    # Graph

    graph = create_research_graph(
        models=agent_models,
        session_factory=SessionLocal,
        search_provider=search_provider,
        document_retriever=document_retriever,
        document_extractor=document_extractor,
    )

    # Workflow service

    workflow_service = ResearchWorkflowService(
        graph=graph,
        session_factory=SessionLocal,
    )

    # Recovery coordinator

    recovery_service = ResearchRecoveryService(
        workflow_service=workflow_service,
        session_factory=SessionLocal,
    )

    return ResearchRecoveryWorker(
        recovery_service=recovery_service,
    )


# ------------------------------------------------------------
# Structured logging
# ------------------------------------------------------------

def install_json_logging():

    """
    Install a JSON handler for the recovery logger.

    This does not clear or replace the application's
    existing root logging handlers.

    Returns the installed handler so it can be removed
    when the worker exits.
    """

    handler = logging.StreamHandler(
        sys.stderr
    )

    handler.setFormatter(
        JsonLogFormatter()
    )

    logger.addHandler(handler)

    logger.setLevel(logging.INFO)

    return handler


# ------------------------------------------------------------
# Continuous recovery
# ------------------------------------------------------------

def run_continuous(
    worker,
    interval,
    limit,
    health_file=None,
):

    monitor = None
    cycle_started_at = None

    if health_file is not None:

        monitor = RecoveryHealthMonitor(
            health_path=health_file,
        )

    ownership = (
        RecoveryHealthOwnership(health_file)
        if health_file is not None
        else nullcontext()
    )

    def on_cycle_start():

        nonlocal cycle_started_at

        cycle_started_at = time.perf_counter()

        if monitor is not None:
            monitor.cycle_started()

    def on_cycle_completed(summary):

        if monitor is not None:

            monitor.cycle_completed(
                summary,
                cycle_started_at,
            )

    def on_cycle_error(error):

        if monitor is not None:

            monitor.cycle_failed(
                error,
                cycle_started_at
                if cycle_started_at is not None
                else time.perf_counter(),
            )

    scheduler = ResearchRecoveryScheduler(
        worker=worker,
        interval_seconds=interval,
        batch_limit=limit,
        on_cycle=on_cycle_completed,
        on_cycle_start=on_cycle_start,
        on_cycle_error=on_cycle_error,
    )

    original_handlers = {}
    json_handler = None

    def request_shutdown(signum, frame):

        print(
            "\nShutdown requested. "
            "Waiting for the active recovery cycle...",
            flush=True,
        )

        scheduler.request_stop()

    def publish_monitor_state(method_name):

        if monitor is None:
            return

        try:
            getattr(
                monitor,
                method_name,
            )()

        except Exception:
            logger.exception(
                "Failed to publish recovery health state: %s",
                method_name,
            )

    # Ownership is held for the complete lifecycle,
    # including final health publication.

    with ownership:

        try:

            if monitor is not None:
                json_handler = install_json_logging()

            # Register cross-platform signal handlers.

            for signal_name in (
                "SIGINT",
                "SIGTERM",
                "SIGBREAK",
            ):

                signum = getattr(
                    signal,
                    signal_name,
                    None,
                )

                if signum is None:
                    continue

                original_handlers[signum] = (
                    signal.getsignal(signum)
                )

                signal.signal(
                    signum,
                    request_shutdown,
                )

            publish_monitor_state(
                "started"
            )

            print(
                "Continuous recovery started. "
                "Press Ctrl+C to stop.",
                flush=True,
            )

            # Execute until shutdown is requested.

            statistics = scheduler.run_forever()

            print()
            print("Continuous recovery stopped.")
            print(f"Cycles: {statistics.cycles}")
            print(f"Resumed: {statistics.resumed}")
            print(f"Paused: {statistics.paused}")
            print(f"Skipped: {statistics.skipped}")

            print(
                f"Failed sessions: {statistics.failed}"
            )

            print(
                f"Cycle errors: {statistics.cycle_errors}"
            )

            print(
                "Monitoring errors: "
                f"{statistics.monitor_errors}"
            )

            return 0

        finally:

            # Publish shutdown state independently.
            # A failed write must not prevent the
            # remaining cleanup operations.

            publish_monitor_state(
                "stopping"
            )

            publish_monitor_state(
                "stopped"
            )

            # Restore original signal handlers.

            for signum, handler in (
                original_handlers.items()
            ):

                try:
                    signal.signal(
                        signum,
                        handler,
                    )

                except Exception:
                    logger.exception(
                        "Failed to restore signal handler %s",
                        signum,
                    )

            # Remove only the handler installed here.

            if json_handler is not None:

                logger.removeHandler(
                    json_handler
                )

                json_handler.close()


# ------------------------------------------------------------
# Worker entry point
# ------------------------------------------------------------

def run(
    argv=None,
    worker_factory=None,
):

    args = parse_arguments(
        argv
    )

    if worker_factory is None:
        worker_factory = create_production_worker

    print()
    print("RESEARCH RECOVERY WORKER")
    print("========================")
    print()

    if args.continuous:

        print("Mode: continuous")
        print(f"Polling interval: {args.interval}s")
        print(f"Batch limit: {args.limit}")

    elif args.session_id is not None:

        print("Mode: targeted recovery")
        print(f"Session: {args.session_id}")

    else:

        print("Mode: single batch cycle")
        print(f"Batch limit: {args.limit}")

    print()

    try:

        worker = worker_factory()

        if args.continuous:

            return run_continuous(
                worker=worker,
                interval=args.interval,
                limit=args.limit,
                health_file=args.health_file,
            )

        if args.session_id is not None:

            summary = worker.run_session(
                session_id=args.session_id,
            )

        else:

            summary = worker.run_once(
                limit=args.limit,
            )

    except Exception as exc:

        print(
            "Recovery worker failed:",
            file=sys.stderr,
        )

        print(
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

        return 2

    if summary.failed > 0:

        print(
            "Recovery cycle completed "
            "with session failures."
        )

        return 1

    if (
        args.session_id is not None
        and summary.skipped > 0
    ):

        print(
            "Targeted session was not eligible "
            "for automatic recovery."
        )

        return 3

    print()

    print(
        "Recovery cycle completed successfully."
    )

    return 0


def main():

    return run()


if __name__ == "__main__":

    sys.exit(
        main()
    )
