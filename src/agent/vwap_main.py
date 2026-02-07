"""Entry point for the VWAP reversion trading agent.

Starts the internal FastAPI server in a background thread and runs the
agent scheduler loop in the main asyncio event loop.
"""

import asyncio
import logging
import os
import threading
from pathlib import Path

import uvicorn

from config.settings import get_settings
from src.agent.api import app, set_config
from src.agent.scheduler import run_agent_loop
from src.agent.vwap_config import VWAPAgentConfig, VWAPStrategyConfig
from src.utils.logging import setup_logging

# Determine project root directory for consistent path resolution
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Use settings-based configuration with agent-specific log file
settings = get_settings()
LOGS_DIR = PROJECT_ROOT / "logs"
setup_logging(
    level=os.environ.get("VWAP_LOG_LEVEL", settings.logging.level),
    format="text",
    file=LOGS_DIR / "vwap.log",
    rotate_size_mb=settings.logging.rotate_size_mb,
    retain_count=settings.logging.retain_count,
)
logger = logging.getLogger(__name__)


def _run_api(config: VWAPAgentConfig) -> None:
    """Run the FastAPI server (blocking - intended for a daemon thread)."""
    uvicorn.run(app, host="0.0.0.0", port=config.api_port, log_level="info")


def main() -> None:
    agent_config = VWAPAgentConfig()
    strategy_config = VWAPStrategyConfig()

    set_config(agent_config)

    logger.info(
        "Starting VWAP reversion agent",
        extra={
            "symbol": agent_config.symbol,
            "interval_minutes": agent_config.interval_minutes,
            "data_provider": agent_config.data_provider,
            "paper": agent_config.paper,
        },
    )

    # Start FastAPI in a daemon thread so the process exits when the main
    # loop ends (or is interrupted).
    api_thread = threading.Thread(target=_run_api, args=(agent_config,), daemon=True)
    api_thread.start()

    # Run the scheduler in the main event loop.
    asyncio.run(
        run_agent_loop(
            agent_config,
            strategy_config,
            strategy_type="vwap",
        )
    )


if __name__ == "__main__":
    main()
