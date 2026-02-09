"""Strategy 32: CCI +/-100 Reversion.

Entry Long: CCI crosses up through -100.
Entry Short: CCI crosses down through +100.
Exit: CCI back to 0 OR time stop 12 OR stop 1.5*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=32,
    name="cci_reversion",
    display_name="CCI +/-100 Reversion",
    philosophy="CCI extremes beyond +/-100 indicate overextension; reversion to zero is the base case.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "threshold", "signal", "time",
          "CCI", "ATR", "range_favor", "scalp"],
    direction="long_short",
    entry_long=[
        crosses_above("cci_20", -100),
    ],
    entry_short=[
        crosses_below("cci_20", 100),
    ],
    exit_long=[
        above("cci_20", 0),
    ],
    exit_short=[
        below("cci_20", 0),
    ],
    atr_stop_mult=1.5,
    time_stop_bars=12,
    required_indicators=["cci_20", "atr_14"],
    details={
        "entry_long": "CCI crosses up through -100",
        "entry_short": "CCI crosses down through +100",
        "exit": "CCI back to 0 OR time stop 12 OR stop 1.5*ATR",
        "indicators": ["CCI(20)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "threshold", "scalp"],
    },
)
