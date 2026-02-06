"""VWAP reversion strategy for the trading agent.

Bets on price reverting to VWAP - buys below VWAP, sells above VWAP.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd

from src.execution.order_manager import Signal, SignalDirection, SignalMetadata

logger = logging.getLogger(__name__)


class VWAPReversionStrategy:
    """VWAP reversion strategy that trades mean reversion to VWAP.

    Uses the ``dist_vwap_60`` feature which measures normalized distance from VWAP:
    - Positive values: price is above VWAP
    - Negative values: price is below VWAP

    Logic (mean reversion):
    - LONG when dist_vwap < short_threshold (price significantly below VWAP)
    - SHORT when dist_vwap > long_threshold (price significantly above VWAP)
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
        feature_name = self.config.vwap_feature

        if feature_name not in latest.index:
            logger.warning(
                "VWAP feature '%s' not found in features", feature_name
            )
            return []

        vwap_distance = latest[feature_name]
        if pd.isna(vwap_distance):
            logger.debug("VWAP distance is NaN, skipping signal generation")
            return []

        logger.debug(
            "Threshold check: %s=%.6f long_threshold=%.6f short_threshold=%.6f",
            feature_name,
            vwap_distance,
            self.config.long_threshold,
            self.config.short_threshold,
        )

        now = timestamp or datetime.now()

        # Mean reversion logic: fade the move away from VWAP
        # Buy when price is significantly BELOW VWAP (expect reversion up)
        # Sell when price is significantly ABOVE VWAP (expect reversion down)
        if vwap_distance < self.config.short_threshold:
            direction = SignalDirection.LONG
            logger.debug(
                "Decision: LONG (VWAP reversion) - %s %.6f < short_threshold %.6f",
                feature_name,
                vwap_distance,
                self.config.short_threshold,
            )
        elif vwap_distance > self.config.long_threshold:
            direction = SignalDirection.SHORT
            logger.debug(
                "Decision: SHORT (VWAP reversion) - %s %.6f > long_threshold %.6f",
                feature_name,
                vwap_distance,
                self.config.long_threshold,
            )
        else:
            direction = SignalDirection.FLAT
            logger.debug(
                "Decision: FLAT - %s %.6f within [%.6f, %.6f]",
                feature_name,
                vwap_distance,
                self.config.short_threshold,
                self.config.long_threshold,
            )

        logger.info(
            "Signal generated: %s %s vwap_dist=%.4f",
            self.symbol,
            direction.value,
            vwap_distance,
        )

        return [
            Signal(
                timestamp=now,
                symbol=self.symbol,
                direction=direction,
                strength=abs(vwap_distance),
                size=self.position_size,
                metadata=SignalMetadata(momentum_value=vwap_distance),
            )
        ]
