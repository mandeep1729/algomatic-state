"""Strategy 44: BB PercentB Reversion.

Entry Long: %B < 0.05 then crosses above 0.1 (using bb_pct column).
Entry Short: %B > 0.95 then crosses below 0.9.
Exit: %B returns to 0.5 OR time 20 OR stop 2*ATR.
"""

from src.strats_prob.conditions import (
    crosses_above,
    crosses_below,
    was_below_then_crosses_above,
    was_above_then_crosses_below,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=44,
    name="bb_percentb_reversion",
    display_name="BB PercentB Reversion",
    philosophy="Bollinger %B at extremes below 0.05 or above 0.95 signals price at band edges; reversion to 0.5 expected.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "threshold", "time",
          "BBANDS", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        was_below_then_crosses_above("bb_pct", 0.1, lookback=5),
    ],
    entry_short=[
        was_above_then_crosses_below("bb_pct", 0.9, lookback=5),
    ],
    exit_long=[
        crosses_above("bb_pct", 0.5),
    ],
    exit_short=[
        crosses_below("bb_pct", 0.5),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["bb_pct", "atr_14"],
    details={
        "entry_long": "%B < 0.05 then crosses above 0.1",
        "entry_short": "%B > 0.95 then crosses below 0.9",
        "exit": "%B returns to 0.5 OR time stop 20 OR stop 2*ATR",
        "indicators": ["BBANDS %B(20,2,2)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "threshold", "swing"],
    },
)
