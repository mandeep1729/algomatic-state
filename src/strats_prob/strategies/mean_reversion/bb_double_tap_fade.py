"""Strategy 29: Bollinger 'Double Tap' Fade.

Entry Long: two closes within last 5 bars below BB lower AND RSI < 35,
            then close back above BB lower.
Entry Short: symmetric above BB upper with RSI > 65.
Exit: target BB middle or 3*ATR; stop 2*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _double_tap_below_bb(lookback: int = 5) -> ConditionFn:
    """True when at least 2 closes in last `lookback` bars were below BB lower."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < lookback:
            return False
        count = 0
        for i in range(idx - lookback, idx):
            close_val = float(df["close"].iloc[i])
            bb_low = float(df["bb_lower"].iloc[i])
            if np.isnan(close_val) or np.isnan(bb_low):
                continue
            if close_val < bb_low:
                count += 1
        return count >= 2
    return _check


def _double_tap_above_bb(lookback: int = 5) -> ConditionFn:
    """True when at least 2 closes in last `lookback` bars were above BB upper."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < lookback:
            return False
        count = 0
        for i in range(idx - lookback, idx):
            close_val = float(df["close"].iloc[i])
            bb_up = float(df["bb_upper"].iloc[i])
            if np.isnan(close_val) or np.isnan(bb_up):
                continue
            if close_val > bb_up:
                count += 1
        return count >= 2
    return _check


strategy = StrategyDef(
    id=29,
    name="bb_double_tap_fade",
    display_name="Bollinger Double Tap Fade",
    philosophy="Multiple touches of Bollinger extremes with RSI confirmation increase reversion probability.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "threshold", "atr_stop", "atr_target",
          "BBANDS", "RSI", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        _double_tap_below_bb(5),
        below("rsi_14", 35),
        crosses_above("close", "bb_lower"),
    ],
    entry_short=[
        _double_tap_above_bb(5),
        above("rsi_14", 65),
        crosses_below("close", "bb_upper"),
    ],
    exit_long=[
        crosses_above("close", "bb_middle"),
    ],
    exit_short=[
        crosses_below("close", "bb_middle"),
    ],
    atr_stop_mult=2.0,
    atr_target_mult=3.0,
    required_indicators=["close", "bb_upper", "bb_middle", "bb_lower", "rsi_14", "atr_14"],
    details={
        "entry_long": "2 closes below BB lower in last 5 bars AND RSI < 35, then close back above BB lower",
        "entry_short": "2 closes above BB upper in last 5 bars AND RSI > 65, then close back below BB upper",
        "exit": "Target BB middle or 3*ATR; stop 2*ATR",
        "indicators": ["BBANDS(20,2,2)", "RSI(14)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "threshold", "swing"],
    },
)
