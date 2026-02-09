"""Strategy 60: ADX Breakout (trend ignition).

Setup: ADX<15 for 10 bars then ADX crosses above 20.
Entry Long: break donchian_high_20.
Entry Short: break donchian_low_20.
Exit: trail 2*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.conditions import (
    breaks_above_level,
    breaks_below_level,
    crosses_above,
    held_for_n_bars,
)
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _adx_ignition(df: pd.DataFrame, idx: int) -> bool:
    """True when ADX was below 15 for 10 bars and now crosses above 20.

    Checks that ADX was consistently below 15 in the lookback window
    and the current bar has ADX crossing above 20.
    """
    if idx < 11:
        return False
    curr_adx = float(df["adx_14"].iloc[idx])
    prev_adx = float(df["adx_14"].iloc[idx - 1])
    if np.isnan(curr_adx) or np.isnan(prev_adx):
        return False
    # ADX must cross above 20 now
    if not (prev_adx <= 20 and curr_adx > 20):
        return False
    # ADX must have been below 15 for 10 bars prior
    window = df["adx_14"].iloc[idx - 11: idx - 1]
    if window.isna().any():
        return False
    return bool((window < 15).all())


strategy = StrategyDef(
    id=60,
    name="adx_breakout",
    display_name="ADX Breakout (Trend Ignition)",
    philosophy="Low ADX followed by a spike signals the start of a new trend.",
    category="breakout",
    tags=["breakout", "regime", "long_short", "threshold", "atr_stop",
          "ADX", "MAX", "MIN", "ATR", "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        _adx_ignition,
        breaks_above_level("donchian_high_20"),
    ],
    entry_short=[
        _adx_ignition,
        breaks_below_level("donchian_low_20"),
    ],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["adx_14", "donchian_high_20", "donchian_low_20", "atr_14"],
    details={
        "entry_long": "ADX<15 for 10 bars then crosses above 20 AND break 20-bar high",
        "entry_short": "ADX<15 for 10 bars then crosses above 20 AND break 20-bar low",
        "exit": "Trail 2*ATR",
        "indicators": ["ADX(14)", "Donchian(20)", "ATR(14)"],
        "tags": ["breakout", "regime", "long_short", "swing"],
    },
)
