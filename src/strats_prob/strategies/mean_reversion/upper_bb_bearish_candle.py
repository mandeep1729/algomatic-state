"""Strategy 48: Upper BB + Bearish Candle.

Entry Short: high > BB upper AND bearish pattern (cdl_engulfing < 0 or cdl_shooting_star < 0).
Exit: BB middle OR time 20 OR stop 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    any_of,
    candle_bearish,
    crosses_below,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=48,
    name="upper_bb_bearish_candle",
    display_name="Upper BB + Bearish Candle",
    philosophy="Bearish candle patterns at Bollinger upper band confirm selling pressure at resistance.",
    category="mean_reversion",
    tags=["mean_reversion", "pattern", "short_only", "pattern", "time",
          "BBANDS", "CDL", "ATR", "range_favor", "swing"],
    direction="short_only",
    entry_long=[],
    entry_short=[
        above("high", "bb_upper"),
        any_of(
            candle_bearish("cdl_engulfing"),
            candle_bearish("cdl_shooting_star"),
        ),
    ],
    exit_long=[],
    exit_short=[
        crosses_below("close", "bb_middle"),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["high", "close", "bb_upper", "bb_middle", "cdl_engulfing",
                         "cdl_shooting_star", "atr_14"],
    details={
        "entry_short": "high > BB upper AND bearish candle pattern (engulfing or shooting star)",
        "entry_long": "N/A (short only)",
        "exit": "BB middle touch OR time stop 20 OR stop 2*ATR",
        "indicators": ["BBANDS(20,2,2)", "CDL_ENGULFING", "CDL_SHOOTING_STAR", "ATR(14)"],
        "tags": ["mean_reversion", "pattern", "short_only", "swing"],
    },
)
