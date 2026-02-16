"""Standalone entry point for the Reviewer Service.

Bootstraps database and messaging, starts the ReviewerOrchestrator,
and blocks until SIGINT/SIGTERM.

Usage:
    python -m src.reviewer.main
"""

import logging
import signal
import sys
import threading
from pathlib import Path

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from config.settings import get_settings
from src.utils.logging import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Bootstrap and run the reviewer service."""
    settings = get_settings()

    # Configure logging
    setup_logging(
        level=settings.logging.level,
        format="text",
        file=PROJECT_ROOT / "logs" / "reviewer-service.log",
        rotate_size_mb=settings.logging.rotate_size_mb,
        retain_count=settings.logging.retain_count,
    )

    logger.info("Starting Reviewer Service")

    # Trigger evaluator registration so get_evaluator() works
    import src.evaluators  # noqa: F401

    # Ensure database is initialized
    from src.data.database.connection import get_db_manager
    db_manager = get_db_manager()
    if not db_manager.health_check():
        logger.error("Database is not healthy, exiting")
        sys.exit(1)
    logger.info("Database connection established")

    # Start the orchestrator
    from src.reviewer.orchestrator import ReviewerOrchestrator
    orchestrator = ReviewerOrchestrator()
    orchestrator.start()

    # Block until signal
    shutdown_event = threading.Event()

    def _signal_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, shutting down", sig_name)
        shutdown_event.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logger.info("Reviewer Service running. Press Ctrl+C to stop.")
    shutdown_event.wait()

    # Clean shutdown
    orchestrator.stop()
    logger.info("Reviewer Service stopped")


if __name__ == "__main__":
    main()
