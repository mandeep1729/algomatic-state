"""Returns and trend features (momentum backbone)."""

from typing import Any

import numpy as np
import pandas as pd

from .base import (
    EPS,
    BaseFeatureCalculator,
    FeatureSpec,
    ema,
    log_return,
    rolling_regression_slope,
    safe_divide,
)


class ReturnFeatureCalculator(BaseFeatureCalculator):
    """Computes return and trend features.

    Features:
        - r1: 1-bar log return
        - r5: 5-bar log return
        - r15: 15-bar log return
        - r60: 60-bar log return
        - cumret_60: Cumulative return over 60 bars
        - ema_diff: Normalized EMA difference (EMA12 - EMA48) / price
        - slope_60: Linear regression slope of log prices
        - trend_strength: |slope_60| / rv_60 (trend vs volatility)

    These features capture direction and persistence at multiple horizons.
    """

    def __init__(
        self,
        short_window: int = 5,
        medium_window: int = 15,
        long_window: int = 60,
        ema_fast: int = 12,
        ema_slow: int = 48,
    ):
        """Initialize ReturnFeatureCalculator.

        Args:
            short_window: Short-term return window (default 5)
            medium_window: Medium-term return window (default 15)
            long_window: Long-term window for slope, cumret, etc. (default 60)
            ema_fast: Fast EMA period (default 12)
            ema_slow: Slow EMA period (default 48)
        """
        self.short_window = short_window
        self.medium_window = medium_window
        self.long_window = long_window
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow

    @property
    def feature_specs(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(
                name="r1",
                description="1-bar log return",
                lookback=2,
                group="returns",
            ),
            FeatureSpec(
                name="r5",
                description="5-bar log return",
                lookback=self.short_window + 1,
                group="returns",
            ),
            FeatureSpec(
                name="r15",
                description="15-bar log return",
                lookback=self.medium_window + 1,
                group="returns",
            ),
            FeatureSpec(
                name="r60",
                description="60-bar log return",
                lookback=self.long_window + 1,
                group="returns",
            ),
            FeatureSpec(
                name="cumret_60",
                description="Cumulative log return over 60 bars",
                lookback=self.long_window,
                group="returns",
            ),
            FeatureSpec(
                name="ema_diff",
                description="Normalized EMA difference: (EMA12 - EMA48) / price",
                lookback=self.ema_slow,
                group="returns",
            ),
            FeatureSpec(
                name="slope_60",
                description="Linear regression slope of log prices over 60 bars",
                lookback=self.long_window,
                group="returns",
            ),
            FeatureSpec(
                name="trend_strength",
                description="Trend strength: |slope_60| / rv_60",
                lookback=self.long_window,
                group="returns",
            ),
        ]

    def compute(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Compute return and trend features.

        Args:
            df: DataFrame with column: close
            **kwargs:
                rv_60: Optional pre-computed 60-bar realized volatility.
                       If not provided, will be computed from r1.

        Returns:
            DataFrame with columns: r1, r5, r15, r60, cumret_60, ema_diff,
                                   slope_60, trend_strength
        """
        close = df["close"]

        result = pd.DataFrame(index=df.index)

        # Log returns at various horizons
        result["r1"] = log_return(close, periods=1)
        result["r5"] = log_return(close, periods=self.short_window)
        result["r15"] = log_return(close, periods=self.medium_window)
        result["r60"] = log_return(close, periods=self.long_window)

        # Cumulative return over long window (sum of r1)
        result["cumret_60"] = result["r1"].rolling(
            window=self.long_window, min_periods=self.long_window
        ).sum()

        # EMA difference (trend proxy)
        ema_fast = ema(close, span=self.ema_fast)
        ema_slow = ema(close, span=self.ema_slow)
        result["ema_diff"] = safe_divide(ema_fast - ema_slow, close)

        # Slope of log prices
        log_prices = np.log(close)
        result["slope_60"] = rolling_regression_slope(log_prices, window=self.long_window)

        # Trend strength: |slope| / volatility
        # Use rv_60 from kwargs if provided, otherwise compute from r1
        rv_60 = kwargs.get("rv_60")
        if rv_60 is None:
            rv_60 = result["r1"].rolling(
                window=self.long_window, min_periods=self.long_window
            ).std()

        result["trend_strength"] = safe_divide(result["slope_60"].abs(), rv_60)

        return result
