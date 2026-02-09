"""Strategy 53: BB Upper/Lower Breakout.

Entry Long: close > BB upper AND BB width rising.
Entry Short: close < BB lower AND BB width rising.
Exit: stop 2*ATR; target 3*ATR; or BB middle cross.
"""

from src.strats_prob.conditions import above, below, crosses_below, crosses_above, rising
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=53,
    name="bb_breakout",
    display_name="BB Upper/Lower Breakout",
    philosophy="Bollinger Band breakout with expanding width confirms volatility expansion.",
    category="breakout",
    tags=["breakout", "long_short", "breakout", "atr_stop", "atr_target",
          "BBANDS", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        above("close", "bb_upper"),
        rising("bb_width", 3),
    ],
    entry_short=[
        below("close", "bb_lower"),
        rising("bb_width", 3),
    ],
    exit_long=[
        crosses_below("close", "bb_middle"),
    ],
    exit_short=[
        crosses_above("close", "bb_middle"),
    ],
    atr_stop_mult=2.0,
    atr_target_mult=3.0,
    required_indicators=["bb_upper", "bb_lower", "bb_middle", "bb_width", "atr_14"],
    details={
        "entry_long": "Close > BB upper AND BB width rising",
        "entry_short": "Close < BB lower AND BB width rising",
        "exit": "BB middle cross OR stop 2*ATR; target 3*ATR",
        "indicators": ["BBANDS(20,2,2)", "ATR(14)"],
        "tags": ["breakout", "long_short", "swing"],
    },
)
