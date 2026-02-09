"""Strategy 23: Moving Average Envelope Break.

Bands: SMA20 +/- 1.5*ATR.
Entry: close breaks above upper (long) or below lower (short).
Exit: return to SMA20 OR target 3*ATR OR stop 2*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.conditions import above, below
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _close_breaks_above_sma_envelope(df: pd.DataFrame, idx: int) -> bool:
    """True when close breaks above SMA20 + 1.5*ATR (was below previous bar)."""
    if idx < 1:
        return False
    close_now = float(df["close"].iloc[idx])
    close_prev = float(df["close"].iloc[idx - 1])
    sma_now = float(df["sma_20"].iloc[idx])
    sma_prev = float(df["sma_20"].iloc[idx - 1])
    atr_now = float(df["atr_14"].iloc[idx])
    atr_prev = float(df["atr_14"].iloc[idx - 1])
    if any(np.isnan(v) or np.isinf(v) for v in [close_now, close_prev, sma_now,
                                                  sma_prev, atr_now, atr_prev]):
        return False
    upper_now = sma_now + 1.5 * atr_now
    upper_prev = sma_prev + 1.5 * atr_prev
    return close_prev <= upper_prev and close_now > upper_now


def _close_breaks_below_sma_envelope(df: pd.DataFrame, idx: int) -> bool:
    """True when close breaks below SMA20 - 1.5*ATR (was above previous bar)."""
    if idx < 1:
        return False
    close_now = float(df["close"].iloc[idx])
    close_prev = float(df["close"].iloc[idx - 1])
    sma_now = float(df["sma_20"].iloc[idx])
    sma_prev = float(df["sma_20"].iloc[idx - 1])
    atr_now = float(df["atr_14"].iloc[idx])
    atr_prev = float(df["atr_14"].iloc[idx - 1])
    if any(np.isnan(v) or np.isinf(v) for v in [close_now, close_prev, sma_now,
                                                  sma_prev, atr_now, atr_prev]):
        return False
    lower_now = sma_now - 1.5 * atr_now
    lower_prev = sma_prev - 1.5 * atr_prev
    return close_prev >= lower_prev and close_now < lower_now


strategy = StrategyDef(
    id=23,
    name="ma_envelope_break",
    display_name="Moving Average Envelope Break",
    philosophy="ATR-based envelope around SMA captures momentum breakouts normalized for volatility.",
    category="trend",
    tags=["trend", "breakout", "long_short", "breakout", "atr_stop", "atr_target",
          "SMA", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        _close_breaks_above_sma_envelope,
    ],
    entry_short=[
        _close_breaks_below_sma_envelope,
    ],
    exit_long=[
        below("close", "sma_20"),
    ],
    exit_short=[
        above("close", "sma_20"),
    ],
    atr_stop_mult=2.0,
    atr_target_mult=3.0,
    required_indicators=["sma_20", "atr_14"],
    details={
        "entry_long": "Close breaks above SMA20 + 1.5*ATR",
        "entry_short": "Close breaks below SMA20 - 1.5*ATR",
        "exit": "Return to SMA20 OR target 3*ATR OR stop 2*ATR",
        "indicators": ["SMA(20)", "ATR(14)"],
        "tags": ["trend", "breakout", "long_short", "swing"],
    },
)
