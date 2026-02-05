"""Anchor and location features (context for continuation)."""

import logging
from typing import Any

import pandas as pd

from .base import EPS, BaseFeatureCalculator, FeatureSpec, ema, safe_divide

logger = logging.getLogger(__name__)


class AnchorFeatureCalculator(BaseFeatureCalculator):
    """Computes anchor and location features.

    Features:
        - vwap_60: Volume-weighted average price over 60 bars
        - dist_vwap_60: Distance from VWAP (normalized)
        - dist_ema_48: Distance from EMA48 (normalized)
        - breakout_20: Distance above 20-bar high (normalized)
        - pullback_depth: Distance below 20-bar high (normalized)

    These features capture where price is relative to key intraday anchors.
    """

    def __init__(
        self,
        vwap_window: int = 60,
        ema_period: int = 48,
        breakout_window: int = 20,
    ):
        """Initialize AnchorFeatureCalculator.

        Args:
            vwap_window: Window for VWAP calculation (default 60)
            ema_period: Period for EMA calculation (default 48)
            breakout_window: Window for breakout/pullback calculation (default 20)
        """
        self.vwap_window = vwap_window
        self.ema_period = ema_period
        self.breakout_window = breakout_window

    @property
    def feature_specs(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(
                name="vwap_60",
                description="60-bar volume-weighted average price",
                lookback=self.vwap_window,
                group="anchor",
            ),
            FeatureSpec(
                name="dist_vwap_60",
                description="Distance from VWAP: (C - VWAP) / C",
                lookback=self.vwap_window,
                group="anchor",
            ),
            FeatureSpec(
                name="dist_ema_48",
                description="Distance from EMA48: (C - EMA48) / C",
                lookback=self.ema_period,
                group="anchor",
            ),
            FeatureSpec(
                name="breakout_20",
                description="Breakout from 20-bar high: (C - high_20) / C",
                lookback=self.breakout_window,
                group="anchor",
            ),
            FeatureSpec(
                name="pullback_depth",
                description="Pullback from 20-bar high: (high_20 - C) / high_20",
                lookback=self.breakout_window,
                group="anchor",
            ),
        ]

    def compute(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Compute anchor and location features.

        Args:
            df: DataFrame with columns: high, low, close, volume

        Returns:
            DataFrame with columns: vwap_60, dist_vwap_60, dist_ema_48,
                                   breakout_20, pullback_depth
        """
        logger.debug("Computing anchor features for %d rows", len(df))
        result = pd.DataFrame(index=df.index)

        # Typical price for VWAP
        typical_price = (df["high"] + df["low"] + df["close"]) / 3

        # VWAP: rolling sum(price * volume) / sum(volume)
        pv = typical_price * df["volume"]
        rolling_pv = pv.rolling(window=self.vwap_window, min_periods=self.vwap_window).sum()
        rolling_vol = df["volume"].rolling(
            window=self.vwap_window, min_periods=self.vwap_window
        ).sum()
        result["vwap_60"] = safe_divide(rolling_pv, rolling_vol)

        # Distance from VWAP
        result["dist_vwap_60"] = safe_divide(df["close"] - result["vwap_60"], df["close"])

        # Distance from EMA48
        ema_48 = ema(df["close"], span=self.ema_period)
        result["dist_ema_48"] = safe_divide(df["close"] - ema_48, df["close"])

        # Rolling 20-bar high
        rolling_high = df["high"].rolling(
            window=self.breakout_window, min_periods=self.breakout_window
        ).max()

        # Breakout: how far above the rolling high
        result["breakout_20"] = safe_divide(df["close"] - rolling_high, df["close"])

        # Pullback depth: how far below the rolling high
        result["pullback_depth"] = safe_divide(rolling_high - df["close"], rolling_high)

        logger.debug(
            "Anchor features computed: dist_vwap_60 range=[%.4f, %.4f], breakout_20 range=[%.4f, %.4f]",
            result["dist_vwap_60"].min(), result["dist_vwap_60"].max(),
            result["breakout_20"].min(), result["breakout_20"].max()
        )
        return result
