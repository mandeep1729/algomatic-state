"""Entry point for the breakout trading agent.

Starts the internal FastAPI server in a background thread and runs the
agent scheduler loop in the main asyncio event loop.
"""

import asyncio
import logging
import os
import threading
from pathlib import Path

import uvicorn

from src.agent.api import app, set_config
from src.agent.breakout_config import BreakoutAgentConfig, BreakoutStrategyConfig
from src.agent.scheduler import run_agent_loop
from src.utils.logging import setup_logging

setup_logging(
    level=os.environ.get("BREAKOUT_LOG_LEVEL", "INFO"),
    format="text",
    file=Path("logs/breakout.log"),
)
logger = logging.getLogger(__name__)


def _run_api(config: BreakoutAgentConfig) -> None:
    """Run the FastAPI server (blocking - intended for a daemon thread)."""
    uvicorn.run(app, host="0.0.0.0", port=config.api_port, log_level="info")


def main() -> None:
    agent_config = BreakoutAgentConfig()
    strategy_config = BreakoutStrategyConfig()

    set_config(agent_config)

    logger.info(
        "Starting breakout agent",
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
            strategy_type="breakout",
        )
    )


if __name__ == "__main__":
    main()
