"""Strategy 36: Z-Score of Close vs SMA20.

Compute: z = (close - SMA20) / STDDEV(20).
Entry Long: z < -2 AND RSI rising 2 bars.
Entry Short: z > +2 AND RSI falling 2 bars.
Exit: z returns to 0 OR time stop 20 OR stop 2*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.conditions import rising, falling
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _zscore_below(threshold: float) -> ConditionFn:
    """True when z-score of close vs SMA20 is below threshold."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        close_val = float(df["close"].iloc[idx])
        sma = float(df["sma_20"].iloc[idx])
        std = float(df["stddev_20"].iloc[idx])
        if any(np.isnan(v) or np.isinf(v) for v in [close_val, sma, std]):
            return False
        if std == 0:
            return False
        z = (close_val - sma) / std
        return z < threshold
    return _check


def _zscore_above(threshold: float) -> ConditionFn:
    """True when z-score of close vs SMA20 is above threshold."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        close_val = float(df["close"].iloc[idx])
        sma = float(df["sma_20"].iloc[idx])
        std = float(df["stddev_20"].iloc[idx])
        if any(np.isnan(v) or np.isinf(v) for v in [close_val, sma, std]):
            return False
        if std == 0:
            return False
        z = (close_val - sma) / std
        return z > threshold
    return _check


def _zscore_crosses_above(threshold: float) -> ConditionFn:
    """True when z-score crosses above threshold (for exit)."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < 1:
            return False
        for i in [idx, idx - 1]:
            close_val = float(df["close"].iloc[i])
            sma = float(df["sma_20"].iloc[i])
            std = float(df["stddev_20"].iloc[i])
            if any(np.isnan(v) or np.isinf(v) for v in [close_val, sma, std]) or std == 0:
                return False
        z_now = (float(df["close"].iloc[idx]) - float(df["sma_20"].iloc[idx])) / float(df["stddev_20"].iloc[idx])
        z_prev = (float(df["close"].iloc[idx - 1]) - float(df["sma_20"].iloc[idx - 1])) / float(df["stddev_20"].iloc[idx - 1])
        return z_prev <= threshold and z_now > threshold
    return _check


def _zscore_crosses_below(threshold: float) -> ConditionFn:
    """True when z-score crosses below threshold (for exit)."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < 1:
            return False
        for i in [idx, idx - 1]:
            close_val = float(df["close"].iloc[i])
            sma = float(df["sma_20"].iloc[i])
            std = float(df["stddev_20"].iloc[i])
            if any(np.isnan(v) or np.isinf(v) for v in [close_val, sma, std]) or std == 0:
                return False
        z_now = (float(df["close"].iloc[idx]) - float(df["sma_20"].iloc[idx])) / float(df["stddev_20"].iloc[idx])
        z_prev = (float(df["close"].iloc[idx - 1]) - float(df["sma_20"].iloc[idx - 1])) / float(df["stddev_20"].iloc[idx - 1])
        return z_prev >= threshold and z_now < threshold
    return _check


strategy = StrategyDef(
    id=36,
    name="zscore_sma20",
    display_name="Z-Score of Close vs SMA20",
    philosophy="Extreme z-scores indicate statistical overextension; reversion to the mean is expected.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "threshold", "time",
          "SMA", "STDDEV", "RSI", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        _zscore_below(-2.0),
        rising("rsi_14", 2),
    ],
    entry_short=[
        _zscore_above(2.0),
        falling("rsi_14", 2),
    ],
    exit_long=[
        _zscore_crosses_above(0.0),
    ],
    exit_short=[
        _zscore_crosses_below(0.0),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["close", "sma_20", "stddev_20", "rsi_14", "atr_14"],
    details={
        "entry_long": "z-score < -2 AND RSI rising 2 bars",
        "entry_short": "z-score > +2 AND RSI falling 2 bars",
        "exit": "z-score returns to 0 OR time stop 20 OR stop 2*ATR",
        "indicators": ["SMA(20)", "STDDEV(20)", "RSI(14)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "threshold", "swing"],
    },
)
