"""Strategy 55: ATR Channel Breakout.

Bands: SMA20 +/- 2*ATR.
Entry: close breaks beyond band in either direction.
Exit: return to SMA20 OR target 4*ATR OR stop 2.5*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.conditions import crosses_above, crosses_below
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _close_above_upper_channel(df: pd.DataFrame, idx: int) -> bool:
    """True when close breaks above SMA20 + 2*ATR."""
    if idx < 1:
        return False
    close_now = float(df["close"].iloc[idx])
    close_prev = float(df["close"].iloc[idx - 1])
    sma_now = float(df["sma_20"].iloc[idx])
    sma_prev = float(df["sma_20"].iloc[idx - 1])
    atr_now = float(df["atr_14"].iloc[idx])
    atr_prev = float(df["atr_14"].iloc[idx - 1])
    if any(np.isnan(v) or np.isinf(v) for v in [close_now, close_prev, sma_now, sma_prev, atr_now, atr_prev]):
        return False
    upper_now = sma_now + 2.0 * atr_now
    upper_prev = sma_prev + 2.0 * atr_prev
    return close_prev <= upper_prev and close_now > upper_now


def _close_below_lower_channel(df: pd.DataFrame, idx: int) -> bool:
    """True when close breaks below SMA20 - 2*ATR."""
    if idx < 1:
        return False
    close_now = float(df["close"].iloc[idx])
    close_prev = float(df["close"].iloc[idx - 1])
    sma_now = float(df["sma_20"].iloc[idx])
    sma_prev = float(df["sma_20"].iloc[idx - 1])
    atr_now = float(df["atr_14"].iloc[idx])
    atr_prev = float(df["atr_14"].iloc[idx - 1])
    if any(np.isnan(v) or np.isinf(v) for v in [close_now, close_prev, sma_now, sma_prev, atr_now, atr_prev]):
        return False
    lower_now = sma_now - 2.0 * atr_now
    lower_prev = sma_prev - 2.0 * atr_prev
    return close_prev >= lower_prev and close_now < lower_now


strategy = StrategyDef(
    id=55,
    name="atr_channel_breakout",
    display_name="ATR Channel Breakout",
    philosophy="Breakout from an ATR-based envelope around SMA20 signals strong directional moves.",
    category="breakout",
    tags=["breakout", "long_short", "breakout", "atr_stop", "atr_target",
          "ATR", "SMA", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        _close_above_upper_channel,
    ],
    entry_short=[
        _close_below_lower_channel,
    ],
    exit_long=[
        crosses_below("close", "sma_20"),
    ],
    exit_short=[
        crosses_above("close", "sma_20"),
    ],
    atr_stop_mult=2.5,
    atr_target_mult=4.0,
    required_indicators=["sma_20", "atr_14"],
    details={
        "entry_long": "Close breaks above SMA20 + 2*ATR",
        "entry_short": "Close breaks below SMA20 - 2*ATR",
        "exit": "Return to SMA20 OR target 4*ATR OR stop 2.5*ATR",
        "indicators": ["SMA(20)", "ATR(14)"],
        "tags": ["breakout", "long_short", "swing"],
    },
)
