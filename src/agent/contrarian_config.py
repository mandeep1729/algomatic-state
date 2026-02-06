"""Contrarian agent configuration via environment variables."""

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class ContrarianAgentConfig(BaseSettings):
    """Configuration for the contrarian trading agent.

    All fields are read from environment variables with the ``CONTRARIAN_`` prefix.
    """

    model_config = SettingsConfigDict(env_prefix="CONTRARIAN_")

    symbol: str = "AAPL"
    interval_minutes: int = 15
    data_provider: str = "alpaca"
    lookback_days: int = 5
    position_size_dollars: float = 1
    paper: bool = True
    api_port: int = 8001

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.debug(
            "ContrarianAgentConfig loaded: symbol=%s, interval=%d min, provider=%s, paper=%s",
            self.symbol,
            self.interval_minutes,
            self.data_provider,
            self.paper,
        )


class ContrarianStrategyConfig(BaseSettings):
    """Strategy configuration for the contrarian agent.

    All fields are read from environment variables with the ``CONTRARIAN_STRATEGY_`` prefix.
    """

    model_config = SettingsConfigDict(env_prefix="CONTRARIAN_STRATEGY_")

    momentum_feature: str = "r5"
    long_threshold: float = 0.001
    short_threshold: float = -0.001
    min_regime_sharpe: float = 0.0
    enable_regime_filter: bool = True
    enable_pattern_matching: bool = True
    enable_dynamic_sizing: bool = True
