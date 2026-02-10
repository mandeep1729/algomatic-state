"""Strategy 64: Pivot Breakout (floor pivots proxy).

Use typical_price_sma_20 as pivot proxy.
Entry: close > typical_price_sma_20 + 1*ATR (long) / < typical_price_sma_20 - 1*ATR (short).
Exit: time 15 OR stop 1.5*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _close_above_pivot_plus_atr(df: pd.DataFrame, idx: int) -> bool:
    """True when close breaks above pivot proxy + 1*ATR."""
    if idx < 1:
        return False
    close_now = float(df["close"].iloc[idx])
    close_prev = float(df["close"].iloc[idx - 1])
    pivot_now = float(df["typical_price_sma_20"].iloc[idx])
    pivot_prev = float(df["typical_price_sma_20"].iloc[idx - 1])
    atr_now = float(df["atr_14"].iloc[idx])
    atr_prev = float(df["atr_14"].iloc[idx - 1])
    if any(np.isnan(v) or np.isinf(v) for v in [close_now, close_prev, pivot_now, pivot_prev, atr_now, atr_prev]):
        return False
    level_now = pivot_now + atr_now
    level_prev = pivot_prev + atr_prev
    return close_prev <= level_prev and close_now > level_now


def _close_below_pivot_minus_atr(df: pd.DataFrame, idx: int) -> bool:
    """True when close breaks below pivot proxy - 1*ATR."""
    if idx < 1:
        return False
    close_now = float(df["close"].iloc[idx])
    close_prev = float(df["close"].iloc[idx - 1])
    pivot_now = float(df["typical_price_sma_20"].iloc[idx])
    pivot_prev = float(df["typical_price_sma_20"].iloc[idx - 1])
    atr_now = float(df["atr_14"].iloc[idx])
    atr_prev = float(df["atr_14"].iloc[idx - 1])
    if any(np.isnan(v) or np.isinf(v) for v in [close_now, close_prev, pivot_now, pivot_prev, atr_now, atr_prev]):
        return False
    level_now = pivot_now - atr_now
    level_prev = pivot_prev - atr_prev
    return close_prev >= level_prev and close_now < level_now


strategy = StrategyDef(
    id=64,
    name="pivot_breakout",
    display_name="Pivot Breakout (Floor Pivots Proxy)",
    philosophy="Classic floor pivot breakout using typical price SMA as proxy.",
    category="breakout",
    tags=["breakout", "long_short", "breakout", "time",
          "SMA", "ATR", "vol_expand", "scalp"],
    direction="long_short",
    entry_long=[
        _close_above_pivot_plus_atr,
    ],
    entry_short=[
        _close_below_pivot_minus_atr,
    ],
    exit_long=[],
    exit_short=[],
    atr_stop_mult=1.5,
    time_stop_bars=15,
    required_indicators=["typical_price_sma_20", "atr_14"],
    details={
        "entry_long": "Close > typical_price_sma_20 + 1*ATR",
        "entry_short": "Close < typical_price_sma_20 - 1*ATR",
        "exit": "Time 15 bars OR stop 1.5*ATR",
        "indicators": ["Typical Price SMA(20)", "ATR(14)"],
        "tags": ["breakout", "long_short", "scalp"],
    },
)
