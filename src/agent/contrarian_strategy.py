"""Contrarian strategy for the trading agent.

Bets against momentum - buys dips, sells rips.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from config.settings import StrategyConfig
from src.execution.order_manager import Signal, SignalDirection, SignalMetadata

logger = logging.getLogger(__name__)


class ContrarianStrategy:
    """Contrarian strategy that bets against momentum.

    Compares a configurable momentum feature (e.g. ``r5``) against
    thresholds but inverts the signals:
    - LONG when momentum is negative (buy the dip)
    - SHORT when momentum is positive (fade the rally)
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

        logger.debug(
            "Signal input: %d rows, latest=%s, features=%s",
            len(features),
            features.index[-1],
            list(features.columns),
        )

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

        logger.debug(
            "Threshold check: %s=%.6f long_threshold=%.6f short_threshold=%.6f",
            feature_name,
            momentum_value,
            self.config.long_threshold,
            self.config.short_threshold,
        )

        now = timestamp or datetime.now()

        # Contrarian logic: INVERT the momentum signals
        # Buy when momentum is negative (price dropped -> expect reversal up)
        # Sell when momentum is positive (price spiked -> expect reversal down)
        if momentum_value < self.config.short_threshold:
            direction = SignalDirection.LONG
            logger.debug(
                "Decision: LONG (contrarian) - momentum %.6f < short_threshold %.6f",
                momentum_value,
                self.config.short_threshold,
            )
        elif momentum_value > self.config.long_threshold:
            direction = SignalDirection.SHORT
            logger.debug(
                "Decision: SHORT (contrarian) - momentum %.6f > long_threshold %.6f",
                momentum_value,
                self.config.long_threshold,
            )
        else:
            direction = SignalDirection.FLAT
            logger.debug(
                "Decision: FLAT - momentum %.6f within [%.6f, %.6f]",
                momentum_value,
                self.config.short_threshold,
                self.config.long_threshold,
            )

        logger.info(
            "Signal generated: %s %s momentum=%.4f (contrarian)",
            self.symbol,
            direction.value,
            momentum_value,
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
