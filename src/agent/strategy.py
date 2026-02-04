"""Momentum strategy for the trading agent."""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from config.settings import StrategyConfig
from src.execution.order_manager import Signal, SignalDirection, SignalMetadata

logger = logging.getLogger(__name__)


class MomentumStrategy:
    """Simple momentum strategy that implements the BaseStrategy protocol.

    Compares a configurable momentum feature (e.g. ``r5``) against
    long/short thresholds to produce trading signals.
    """

    def __init__(
        self,
        config: StrategyConfig,
        symbol: str,
        position_size: float,
    ):
        self.config = config
        self.symbol = symbol
        self.position_size = position_size

    def generate_signals(
        self,
        features: pd.DataFrame,
        timestamp: datetime | None = None,
        state: np.ndarray | None = None,
    ) -> list[Signal]:
        if features.empty:
            logger.debug("No features available for signal generation")
            return []

        latest = features.iloc[-1]
        feature_name = self.config.momentum_feature

        if feature_name not in latest.index:
            logger.warning(
                "Momentum feature '%s' not found in features", feature_name
            )
            return []

        momentum_value = latest[feature_name]
        if pd.isna(momentum_value):
            logger.debug("Momentum value is NaN, skipping signal generation")
            return []

        now = timestamp or datetime.now()

        if momentum_value > self.config.long_threshold:
            direction = SignalDirection.LONG
        elif momentum_value < self.config.short_threshold:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.FLAT

        logger.info(
            "Signal generated: %s %s momentum=%.4f",
            self.symbol, direction.value, momentum_value,
        )

        return [
            Signal(
                timestamp=now,
                symbol=self.symbol,
                direction=direction,
                strength=abs(momentum_value),
                size=self.position_size,
                metadata=SignalMetadata(momentum_value=momentum_value),
            )
        ]
