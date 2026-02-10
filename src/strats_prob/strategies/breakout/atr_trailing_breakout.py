"""Strategy 69: ATR Trailing Breakout.

Entry Long: close > prior close + 1*ATR.
Entry Short: close < prior close - 1*ATR.
Exit: trail 2*ATR or time 20.
"""

import numpy as np
import pandas as pd

from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _close_jumps_up_by_atr(df: pd.DataFrame, idx: int) -> bool:
    """True when close exceeds prior close by more than 1*ATR."""
    if idx < 1:
        return False
    close_now = float(df["close"].iloc[idx])
    close_prev = float(df["close"].iloc[idx - 1])
    atr = float(df["atr_14"].iloc[idx])
    if any(np.isnan(v) or np.isinf(v) for v in [close_now, close_prev, atr]):
        return False
    return close_now > close_prev + atr


def _close_drops_by_atr(df: pd.DataFrame, idx: int) -> bool:
    """True when close is below prior close by more than 1*ATR."""
    if idx < 1:
        return False
    close_now = float(df["close"].iloc[idx])
    close_prev = float(df["close"].iloc[idx - 1])
    atr = float(df["atr_14"].iloc[idx])
    if any(np.isnan(v) or np.isinf(v) for v in [close_now, close_prev, atr]):
        return False
    return close_now < close_prev - atr


strategy = StrategyDef(
    id=69,
    name="atr_trailing_breakout",
    display_name="ATR Trailing Breakout",
    philosophy="A single-bar move exceeding 1*ATR signals strong directional conviction.",
    category="breakout",
    tags=["breakout", "long_short", "breakout", "trailing",
          "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        _close_jumps_up_by_atr,
    ],
    entry_short=[
        _close_drops_by_atr,
    ],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["atr_14"],
    details={
        "entry_long": "Close > prior close + 1*ATR",
        "entry_short": "Close < prior close - 1*ATR",
        "exit": "Trail 2*ATR or time 20 bars",
        "indicators": ["ATR(14)"],
        "tags": ["breakout", "long_short", "swing"],
    },
)
