"""Agent configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentConfig(BaseSettings):
    """Configuration for the momentum trading agent.

    All fields are read from environment variables with the ``AGENT_`` prefix.
    """

    model_config = SettingsConfigDict(env_prefix="AGENT_")

    symbol: str = "AAPL"
    interval_minutes: int = 15
    data_provider: str = "alpaca"
    lookback_days: int = 5
    position_size_dollars: float = 10000
    paper: bool = True
    api_port: int = 8000
