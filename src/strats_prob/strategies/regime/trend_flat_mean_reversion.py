"""Strategy 96: Mean Reversion Only When Trend Flat.

Filter: abs(linearreg_slope_20) < small epsilon threshold.
Entry: RSI crosses up through 30 (long) or down through 70 (short).
Exit: RSI 50 OR time 25 OR stop 2*ATR.
"""

import numpy as np

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _flat_slope(epsilon: float = 0.001) -> ConditionFn:
    """True when the linear regression slope is near zero (flat trend).

    The epsilon threshold is intentionally small to identify truly trendless
    periods. Adjust per instrument if needed.
    """
    def _check(df, idx):
        slope = float(df["linearreg_slope_20"].iloc[idx])
        if np.isnan(slope):
            return False
        return abs(slope) < epsilon
    return _check


strategy = StrategyDef(
    id=96,
    name="trend_flat_mean_reversion",
    display_name="Trend Flat Mean Reversion",
    philosophy="Mean reversion strategies work best when there is no underlying trend; "
               "filtering by slope near zero avoids fighting momentum.",
    category="regime",
    tags=["multi_filter", "mean_reversion", "regime", "long_short", "threshold",
          "time", "SMA", "LINEARREG_SLOPE", "RSI", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        _flat_slope(0.001),
        crosses_above("rsi_14", 30),
    ],
    entry_short=[
        _flat_slope(0.001),
        crosses_below("rsi_14", 70),
    ],
    exit_long=[
        above("rsi_14", 50),
    ],
    exit_short=[
        below("rsi_14", 50),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=25,
    required_indicators=["linearreg_slope_20", "rsi_14", "atr_14"],
    details={
        "entry_long": "abs(linearreg_slope_20) < epsilon AND RSI crosses up through 30",
        "entry_short": "abs(linearreg_slope_20) < epsilon AND RSI crosses down through 70",
        "exit": "RSI reaches 50 OR time stop 25 bars OR stop 2*ATR",
        "indicators": ["LINEARREG_SLOPE(20)", "RSI(14)", "ATR(14)"],
        "tags": ["multi_filter", "mean_reversion", "regime", "long_short", "swing"],
    },
)
