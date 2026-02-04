"""Momentum strategy for the trading agent."""

from datetime import datetime

import numpy as np
import pandas as pd

from config.settings import StrategyConfig
from src.execution.order_manager import Signal, SignalDirection, SignalMetadata


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
            return []

        latest = features.iloc[-1]
        feature_name = self.config.momentum_feature

        if feature_name not in latest.index:
            return []

        momentum_value = latest[feature_name]
        if pd.isna(momentum_value):
            return []

        now = timestamp or datetime.now()

        if momentum_value > self.config.long_threshold:
            direction = SignalDirection.LONG
        elif momentum_value < self.config.short_threshold:
            direction = SignalDirection.SHORT
        else:
            direction = SignalDirection.FLAT

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
