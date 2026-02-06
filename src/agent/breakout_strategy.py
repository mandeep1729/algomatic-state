"""Breakout strategy for the trading agent.

Trades breakouts above recent highs and breakdowns below recent lows.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from src.execution.order_manager import Signal, SignalDirection, SignalMetadata

logger = logging.getLogger(__name__)


class BreakoutStrategy:
    """Breakout strategy that trades price breaks above/below recent extremes.

    Uses the ``breakout_20`` feature which measures distance from 20-bar high:
    - Positive values: price is at or above recent high (breakout)
    - Negative values: price is below recent high (potential breakdown)

    Logic:
    - LONG when breakout_20 > long_threshold (price breaking above highs)
    - SHORT when breakout_20 < short_threshold (price breaking down)
    """

    def __init__(
        self,
        config,
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

        logger.debug(
            "Signal input: %d rows, latest=%s, features=%s",
            len(features),
            features.index[-1],
            list(features.columns),
        )

        latest = features.iloc[-1]
        feature_name = self.config.breakout_feature

        if feature_name not in latest.index:
            logger.warning(
                "Breakout feature '%s' not found in features", feature_name
            )
            return []

        breakout_value = latest[feature_name]
        if pd.isna(breakout_value):
            logger.debug("Breakout value is NaN, skipping signal generation")
            return []

        logger.debug(
            "Threshold check: %s=%.6f long_threshold=%.6f short_threshold=%.6f",
            feature_name,
            breakout_value,
            self.config.long_threshold,
            self.config.short_threshold,
        )

        now = timestamp or datetime.now()

        # Breakout logic: follow the break direction
        if breakout_value > self.config.long_threshold:
            direction = SignalDirection.LONG
            logger.debug(
                "Decision: LONG (breakout) - %s %.6f > long_threshold %.6f",
                feature_name,
                breakout_value,
                self.config.long_threshold,
            )
        elif breakout_value < self.config.short_threshold:
            direction = SignalDirection.SHORT
            logger.debug(
                "Decision: SHORT (breakdown) - %s %.6f < short_threshold %.6f",
                feature_name,
                breakout_value,
                self.config.short_threshold,
            )
        else:
            direction = SignalDirection.FLAT
            logger.debug(
                "Decision: FLAT - %s %.6f within [%.6f, %.6f]",
                feature_name,
                breakout_value,
                self.config.short_threshold,
                self.config.long_threshold,
            )

        logger.info(
            "Signal generated: %s %s breakout=%.4f",
            self.symbol,
            direction.value,
            breakout_value,
        )

        return [
            Signal(
                timestamp=now,
                symbol=self.symbol,
                direction=direction,
                strength=abs(breakout_value),
                size=self.position_size,
                metadata=SignalMetadata(momentum_value=breakout_value),
            )
        ]
