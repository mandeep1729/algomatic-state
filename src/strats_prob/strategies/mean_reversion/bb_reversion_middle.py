"""Strategy 28: Bollinger Band Reversion to Middle.

Entry Long: close was below BB lower last bar and crosses back above.
Entry Short: close was above BB upper last bar and crosses back below.
Exit: BB middle touch OR time stop 20 OR stop 2*ATR.
"""

from src.strats_prob.conditions import (
    crosses_above,
    crosses_below,
    was_above_then_crosses_below,
    was_below_then_crosses_above,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=28,
    name="bb_reversion_middle",
    display_name="Bollinger Band Reversion to Middle",
    philosophy="Price bouncing off Bollinger extremes tends to revert toward the middle band.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "threshold", "signal", "time",
          "BBANDS", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("close", "bb_lower"),
    ],
    entry_short=[
        crosses_below("close", "bb_upper"),
    ],
    exit_long=[
        crosses_above("close", "bb_middle"),
    ],
    exit_short=[
        crosses_below("close", "bb_middle"),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["close", "bb_upper", "bb_middle", "bb_lower", "atr_14"],
    details={
        "entry_long": "Close was below BB lower and crosses back above",
        "entry_short": "Close was above BB upper and crosses back below",
        "exit": "BB middle touch OR time stop 20 OR stop 2*ATR",
        "indicators": ["BBANDS(20,2,2)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "threshold", "swing"],
    },
)
