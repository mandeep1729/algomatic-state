"""VWAP reversion agent configuration via environment variables."""

import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class VWAPAgentConfig(BaseSettings):
    """Configuration for the VWAP reversion trading agent.

    All fields are read from environment variables with the ``VWAP_`` prefix.
    """

    model_config = SettingsConfigDict(env_prefix="VWAP_")

    symbol: str = "AAPL"
    interval_minutes: int = 15
    data_provider: str = "alpaca"
    lookback_days: int = 5
    position_size_dollars: float = 1
    paper: bool = True
    api_port: int = 8003
    atr_stop_mult: float = 1.5
    atr_target_mult: float = 3.0

    @property
    def timeframe(self) -> str:
        """Map interval_minutes to a supported timeframe string."""
        if self.interval_minutes <= 1:
            return "1Min"
        elif self.interval_minutes <= 15:
            return "15Min"
        elif self.interval_minutes <= 60:
            return "1Hour"
        else:
            return "1Day"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.debug(
            "VWAPAgentConfig loaded: symbol=%s, interval=%d min, timeframe=%s, provider=%s, paper=%s",
            self.symbol,
            self.interval_minutes,
            self.timeframe,
            self.data_provider,
            self.paper,
        )


class VWAPStrategyConfig(BaseSettings):
    """Strategy configuration for the VWAP reversion agent.

    All fields are read from environment variables with the ``VWAP_STRATEGY_`` prefix.
    """

    model_config = SettingsConfigDict(env_prefix="VWAP_STRATEGY_")

    vwap_feature: str = "dist_vwap_60"
    long_threshold: float = 0.005  # Price 0.5% above VWAP -> SHORT (fade)
    short_threshold: float = -0.005  # Price 0.5% below VWAP -> LONG (fade)
    min_regime_sharpe: float = 0.0
    enable_regime_filter: bool = True
    enable_pattern_matching: bool = True
    enable_dynamic_sizing: bool = True
