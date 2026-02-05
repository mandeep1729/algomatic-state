"""Volatility and range features (regime + risk context)."""

import logging
from typing import Any

import pandas as pd

from .base import EPS, BaseFeatureCalculator, FeatureSpec, log_return, safe_divide, zscore

logger = logging.getLogger(__name__)


class VolatilityFeatureCalculator(BaseFeatureCalculator):
    """Computes volatility and range features.

    Features:
        - rv_15: 15-bar realized volatility (std of returns)
        - rv_60: 60-bar realized volatility
        - range_1: Normalized bar range (H - L) / C
        - atr_60: Average range over 60 bars
        - range_z_60: Z-score of range
        - vol_of_vol: Volatility of volatility (std of rv_15)

    These features help identify chop, transitions, and volatility regimes.
    """

    def __init__(
        self,
        short_window: int = 15,
        long_window: int = 60,
    ):
        """Initialize VolatilityFeatureCalculator.

        Args:
            short_window: Short-term volatility window (default 15)
            long_window: Long-term volatility window (default 60)
        """
        self.short_window = short_window
        self.long_window = long_window

    @property
    def feature_specs(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(
                name="rv_15",
                description="15-bar realized volatility (std of r1)",
                lookback=self.short_window,
                group="volatility",
            ),
            FeatureSpec(
                name="rv_60",
                description="60-bar realized volatility (std of r1)",
                lookback=self.long_window,
                group="volatility",
            ),
            FeatureSpec(
                name="range_1",
                description="Normalized bar range: (H - L) / C",
                lookback=1,
                group="volatility",
            ),
            FeatureSpec(
                name="atr_60",
                description="Average range over 60 bars",
                lookback=self.long_window,
                group="volatility",
            ),
            FeatureSpec(
                name="range_z_60",
                description="Z-score of range over 60 bars",
                lookback=self.long_window,
                group="volatility",
            ),
            FeatureSpec(
                name="vol_of_vol",
                description="Volatility of volatility: std(rv_15) over 60 bars",
                lookback=self.long_window + self.short_window,
                group="volatility",
            ),
        ]

    def compute(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Compute volatility and range features.

        Args:
            df: DataFrame with columns: high, low, close
            **kwargs:
                r1: Optional pre-computed 1-bar returns.
                    If not provided, will be computed from close.

        Returns:
            DataFrame with columns: rv_15, rv_60, range_1, atr_60,
                                   range_z_60, vol_of_vol
        """
        logger.debug("Computing volatility features for %d rows", len(df))
        result = pd.DataFrame(index=df.index)

        # Get or compute r1
        r1 = kwargs.get("r1")
        if r1 is None:
            r1 = log_return(df["close"], periods=1)

        # Realized volatility at two windows
        result["rv_15"] = r1.rolling(
            window=self.short_window, min_periods=self.short_window
        ).std()
        result["rv_60"] = r1.rolling(
            window=self.long_window, min_periods=self.long_window
        ).std()

        # Normalized bar range
        result["range_1"] = safe_divide(df["high"] - df["low"], df["close"])

        # Average range (ATR-like)
        result["atr_60"] = result["range_1"].rolling(
            window=self.long_window, min_periods=self.long_window
        ).mean()

        # Range z-score
        result["range_z_60"] = zscore(result["range_1"], window=self.long_window)

        # Volatility of volatility
        result["vol_of_vol"] = result["rv_15"].rolling(
            window=self.long_window, min_periods=self.long_window
        ).std()

        logger.debug(
            "Volatility features computed: rv_60 range=[%.6f, %.6f], atr_60 range=[%.6f, %.6f]",
            result["rv_60"].min(), result["rv_60"].max(),
            result["atr_60"].min(), result["atr_60"].max()
        )
        return result
