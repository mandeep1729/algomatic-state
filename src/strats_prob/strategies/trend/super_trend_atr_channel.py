"""Strategy 13: Super Trend-like using ATR Channel (EMA baseline).

Compute: baseline=EMA(20); upper=baseline+2*ATR; lower=baseline-2*ATR.
Entry Long: close > ema_20 + 2*atr_14.
Entry Short: close < ema_20 - 2*atr_14.
Exit: cross back through baseline OR trailing 2*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.conditions import above, below
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _close_above_upper_channel(df: pd.DataFrame, idx: int) -> bool:
    """True when close > EMA20 + 2*ATR (upper channel)."""
    close = float(df["close"].iloc[idx])
    ema = float(df["ema_20"].iloc[idx])
    atr = float(df["atr_14"].iloc[idx])
    if any(np.isnan(v) or np.isinf(v) for v in [close, ema, atr]):
        return False
    return close > ema + 2.0 * atr


def _close_below_lower_channel(df: pd.DataFrame, idx: int) -> bool:
    """True when close < EMA20 - 2*ATR (lower channel)."""
    close = float(df["close"].iloc[idx])
    ema = float(df["ema_20"].iloc[idx])
    atr = float(df["atr_14"].iloc[idx])
    if any(np.isnan(v) or np.isinf(v) for v in [close, ema, atr]):
        return False
    return close < ema - 2.0 * atr


strategy = StrategyDef(
    id=13,
    name="super_trend_atr_channel",
    display_name="Super Trend-like ATR Channel",
    philosophy="ATR channel around EMA captures strong breakouts beyond normal volatility.",
    category="trend",
    tags=["trend", "long_short", "threshold", "trailing", "EMA", "ATR",
          "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        _close_above_upper_channel,
    ],
    entry_short=[
        _close_below_lower_channel,
    ],
    exit_long=[
        below("close", "ema_20"),
    ],
    exit_short=[
        above("close", "ema_20"),
    ],
    atr_stop_mult=2.0,
    trailing_atr_mult=2.0,
    required_indicators=["ema_20", "atr_14"],
    details={
        "entry_long": "Close > EMA20 + 2*ATR (upper channel breakout)",
        "entry_short": "Close < EMA20 - 2*ATR (lower channel breakout)",
        "exit": "Cross back through EMA20 baseline OR trailing 2*ATR",
        "indicators": ["EMA(20)", "ATR(14)"],
        "tags": ["trend", "long_short", "threshold", "swing"],
    },
)
