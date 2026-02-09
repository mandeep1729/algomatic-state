"""Strategy 31: Williams %R Snapback.

Entry Long: WILLR crosses up through -80.
Entry Short: WILLR crosses down through -20.
Exit: WILLR reaches -50 OR time stop 8 OR stop 1.5*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=31,
    name="willr_snapback",
    display_name="Williams %R Snapback",
    philosophy="Williams %R at extreme levels signals exhaustion; snapback toward midpoint is likely.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "threshold", "time",
          "WILLR", "ATR", "range_favor", "scalp"],
    direction="long_short",
    entry_long=[
        crosses_above("willr_14", -80),
    ],
    entry_short=[
        crosses_below("willr_14", -20),
    ],
    exit_long=[
        above("willr_14", -50),
    ],
    exit_short=[
        below("willr_14", -50),
    ],
    atr_stop_mult=1.5,
    time_stop_bars=8,
    required_indicators=["willr_14", "atr_14"],
    details={
        "entry_long": "WILLR crosses up through -80",
        "entry_short": "WILLR crosses down through -20",
        "exit": "WILLR reaches -50 OR time stop 8 OR stop 1.5*ATR",
        "indicators": ["WILLR(14)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "threshold", "scalp"],
    },
)
