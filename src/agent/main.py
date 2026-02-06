"""Entry point for the momentum trading agent.

Starts the internal FastAPI server in a background thread and runs the
agent scheduler loop in the main asyncio event loop.
"""

import asyncio
import logging
import os
import threading
from pathlib import Path

import uvicorn

from config.settings import StrategyConfig
from src.agent.api import app, set_config
from src.agent.config import AgentConfig
from src.agent.scheduler import run_agent_loop
from src.utils.logging import setup_logging

setup_logging(level=os.environ.get("AGENT_LOG_LEVEL", "INFO"), format="text", file=Path("logs/agent.log"))
logger = logging.getLogger(__name__)


def _run_api(config: AgentConfig) -> None:
    """Run the FastAPI server (blocking — intended for a daemon thread)."""
    uvicorn.run(app, host="0.0.0.0", port=config.api_port, log_level="info")


def _create_provider(data_provider: str):
    """Create the appropriate MarketDataProvider from config name."""
    if data_provider == "finnhub":
        from src.marketdata.finnhub_provider import FinnhubProvider
        return FinnhubProvider()
    else:
        from src.marketdata.alpaca_provider import AlpacaProvider
        return AlpacaProvider()


def main() -> None:
    agent_config = AgentConfig()
    strategy_config = StrategyConfig()

    set_config(agent_config)

    logger.info(
        "Starting momentum agent",
        extra={
            "symbol": agent_config.symbol,
            "interval_minutes": agent_config.interval_minutes,
            "data_provider": agent_config.data_provider,
            "paper": agent_config.paper,
        },
    )

    # Start MarketDataOrchestrator so that messaging-based data requests
    # are fulfilled automatically.
    from src.marketdata.orchestrator import MarketDataOrchestrator

    provider = _create_provider(agent_config.data_provider)
    orchestrator = MarketDataOrchestrator(provider)
    orchestrator.start()

    # Start FastAPI in a daemon thread so the process exits when the main
    # loop ends (or is interrupted).
    api_thread = threading.Thread(target=_run_api, args=(agent_config,), daemon=True)
    api_thread.start()

    # Run the scheduler in the main event loop.
    asyncio.run(run_agent_loop(agent_config, strategy_config))


if __name__ == "__main__":
    main()
