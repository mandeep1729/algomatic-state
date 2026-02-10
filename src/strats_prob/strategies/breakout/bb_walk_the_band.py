"""Strategy 63: Bollinger Walk the Band (trend breakout).

Entry Long: 3 consecutive closes above BB upper.
Entry Short: 3 consecutive closes below BB lower.
Exit: first close back inside bands OR trail 2*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.conditions import below, above
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _three_closes_above_bb_upper(df: pd.DataFrame, idx: int) -> bool:
    """True when the last 3 closes are all above BB upper."""
    if idx < 2:
        return False
    for i in range(idx - 2, idx + 1):
        close_val = float(df["close"].iloc[i])
        upper_val = float(df["bb_upper"].iloc[i])
        if np.isnan(close_val) or np.isnan(upper_val):
            return False
        if close_val <= upper_val:
            return False
    return True


def _three_closes_below_bb_lower(df: pd.DataFrame, idx: int) -> bool:
    """True when the last 3 closes are all below BB lower."""
    if idx < 2:
        return False
    for i in range(idx - 2, idx + 1):
        close_val = float(df["close"].iloc[i])
        lower_val = float(df["bb_lower"].iloc[i])
        if np.isnan(close_val) or np.isnan(lower_val):
            return False
        if close_val >= lower_val:
            return False
    return True


strategy = StrategyDef(
    id=63,
    name="bb_walk_the_band",
    display_name="Bollinger Walk the Band",
    philosophy="Sustained closes outside the band indicate strong trend continuation.",
    category="breakout",
    tags=["breakout", "trend", "long_short", "threshold", "trailing",
          "BBANDS", "ATR", "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        _three_closes_above_bb_upper,
    ],
    entry_short=[
        _three_closes_below_bb_lower,
    ],
    exit_long=[
        below("close", "bb_upper"),
    ],
    exit_short=[
        above("close", "bb_lower"),
    ],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["bb_upper", "bb_lower", "atr_14"],
    details={
        "entry_long": "3 consecutive closes above BB upper",
        "entry_short": "3 consecutive closes below BB lower",
        "exit": "First close back inside bands OR trail 2*ATR",
        "indicators": ["BBANDS(20,2,2)", "ATR(14)"],
        "tags": ["breakout", "trend", "long_short", "swing"],
    },
)
