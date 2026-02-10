"""Strategy 17: Trend + Volatility Expansion Confirmation.

Entry Long: ADX>20 AND close breaks above BB upper AND BB width increasing vs 5 bars ago.
Entry Short: ADX>20 AND close breaks below BB lower AND BB width increasing.
Exit: target=3*ATR, stop=2*ATR, or BB middle cross.
"""

import numpy as np
import pandas as pd

from src.strats_prob.conditions import above, below, breaks_above_level, breaks_below_level
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _bb_width_increasing(df: pd.DataFrame, idx: int) -> bool:
    """True when BB width at current bar exceeds BB width 5 bars ago."""
    if idx < 5:
        return False
    curr = float(df["bb_width"].iloc[idx])
    prev = float(df["bb_width"].iloc[idx - 5])
    if any(np.isnan(v) or np.isinf(v) for v in [curr, prev]):
        return False
    return curr > prev


strategy = StrategyDef(
    id=17,
    name="trend_vol_expansion",
    display_name="Trend + Volatility Expansion Confirmation",
    philosophy="Breakout beyond BB bands with expanding width confirms genuine volatility expansion.",
    category="trend",
    tags=["trend", "volatility", "long_short", "breakout", "atr_stop", "atr_target",
          "BBANDS", "ADX", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        above("adx_14", 20),
        breaks_above_level("bb_upper"),
        _bb_width_increasing,
    ],
    entry_short=[
        above("adx_14", 20),
        breaks_below_level("bb_lower"),
        _bb_width_increasing,
    ],
    exit_long=[
        below("close", "bb_middle"),
    ],
    exit_short=[
        above("close", "bb_middle"),
    ],
    atr_stop_mult=2.0,
    atr_target_mult=3.0,
    required_indicators=["adx_14", "bb_upper", "bb_lower", "bb_middle", "bb_width",
                         "atr_14"],
    details={
        "entry_long": "ADX > 20 AND close breaks above BB upper AND BB width increasing",
        "entry_short": "ADX > 20 AND close breaks below BB lower AND BB width increasing",
        "exit": "Target 3*ATR OR stop 2*ATR OR BB middle cross",
        "indicators": ["BBANDS(20,2,2)", "ADX(14)", "ATR(14)"],
        "tags": ["trend", "volatility", "long_short", "breakout", "swing"],
    },
)
