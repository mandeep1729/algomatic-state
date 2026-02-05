"""Agent configuration via environment variables."""

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class AgentConfig(BaseSettings):
    """Configuration for the momentum trading agent.

    All fields are read from environment variables with the ``AGENT_`` prefix.
    """

    model_config = SettingsConfigDict(env_prefix="AGENT_")

    symbol: str = "AAPL"
    interval_minutes: int = 15
    data_provider: str = "alpaca"
    lookback_days: int = 5
    position_size_dollars: float = 1
    paper: bool = True
    api_port: int = 8000

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.debug(
            "AgentConfig loaded: symbol=%s, interval=%d min, provider=%s, paper=%s",
            self.symbol, self.interval_minutes, self.data_provider, self.paper
        )
