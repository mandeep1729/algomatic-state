"""Strategy 67: Inside Bar Breakout (NR7-ish proxy).

Setup: bar range is smallest of last 7 bars.
Entry: break above that bar high (long) / below low (short).
Use narrowest_range condition then next bar break.
Exit: time 10 OR stop 1.5*ATR OR target 2.5*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _prev_bar_narrowest_and_break_above(df: pd.DataFrame, idx: int) -> bool:
    """True when previous bar was the narrowest of last 7 bars and close breaks above its high."""
    if idx < 7:
        return False
    prev_idx = idx - 1
    # Check if previous bar had the narrowest range of last 7 bars
    ranges = df["high"].iloc[prev_idx - 6: prev_idx + 1] - df["low"].iloc[prev_idx - 6: prev_idx + 1]
    if ranges.isna().any():
        return False
    prev_range = float(df["high"].iloc[prev_idx]) - float(df["low"].iloc[prev_idx])
    if prev_range > float(ranges.min()):
        return False
    # Current close breaks above previous bar high
    close_now = float(df["close"].iloc[idx])
    prev_high = float(df["high"].iloc[prev_idx])
    if np.isnan(close_now) or np.isnan(prev_high):
        return False
    return close_now > prev_high


def _prev_bar_narrowest_and_break_below(df: pd.DataFrame, idx: int) -> bool:
    """True when previous bar was the narrowest of last 7 bars and close breaks below its low."""
    if idx < 7:
        return False
    prev_idx = idx - 1
    # Check if previous bar had the narrowest range of last 7 bars
    ranges = df["high"].iloc[prev_idx - 6: prev_idx + 1] - df["low"].iloc[prev_idx - 6: prev_idx + 1]
    if ranges.isna().any():
        return False
    prev_range = float(df["high"].iloc[prev_idx]) - float(df["low"].iloc[prev_idx])
    if prev_range > float(ranges.min()):
        return False
    # Current close breaks below previous bar low
    close_now = float(df["close"].iloc[idx])
    prev_low = float(df["low"].iloc[prev_idx])
    if np.isnan(close_now) or np.isnan(prev_low):
        return False
    return close_now < prev_low


strategy = StrategyDef(
    id=67,
    name="inside_bar_breakout",
    display_name="Inside Bar Breakout (NR7 Proxy)",
    philosophy="Narrowest range bar signals coiled volatility; break of its extremes captures expansion.",
    category="breakout",
    tags=["breakout", "pattern", "long_short", "pattern", "breakout",
          "time", "ATR", "vol_contract", "vol_expand", "scalp"],
    direction="long_short",
    entry_long=[
        _prev_bar_narrowest_and_break_above,
    ],
    entry_short=[
        _prev_bar_narrowest_and_break_below,
    ],
    exit_long=[],
    exit_short=[],
    atr_stop_mult=1.5,
    atr_target_mult=2.5,
    time_stop_bars=10,
    required_indicators=["high", "low", "close", "atr_14"],
    details={
        "entry_long": "Previous bar narrowest of 7 bars AND close breaks above its high",
        "entry_short": "Previous bar narrowest of 7 bars AND close breaks below its low",
        "exit": "Time 10 bars OR stop 1.5*ATR OR target 2.5*ATR",
        "indicators": ["ATR(14)"],
        "tags": ["breakout", "pattern", "long_short", "scalp"],
    },
)
