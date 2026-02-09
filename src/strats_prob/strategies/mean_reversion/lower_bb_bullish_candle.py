"""Strategy 47: Price Touches Lower BB + Bullish Candle.

Entry Long: low < BB lower AND any bullish candle pattern (cdl_engulfing > 0 or cdl_harami > 0).
Exit: BB middle OR time 20 OR stop 2*ATR.
"""

from src.strats_prob.conditions import (
    any_of,
    below,
    candle_bullish,
    crosses_above,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=47,
    name="lower_bb_bullish_candle",
    display_name="Lower BB + Bullish Candle",
    philosophy="Bullish candle patterns at Bollinger lower band confirm buying interest at support.",
    category="mean_reversion",
    tags=["mean_reversion", "pattern", "long_only", "pattern", "time",
          "BBANDS", "CDL", "ATR", "range_favor", "swing"],
    direction="long_only",
    entry_long=[
        below("low", "bb_lower"),
        any_of(
            candle_bullish("cdl_engulfing"),
            candle_bullish("cdl_harami"),
            candle_bullish("cdl_hammer"),
        ),
    ],
    entry_short=[],
    exit_long=[
        crosses_above("close", "bb_middle"),
    ],
    exit_short=[],
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["low", "close", "bb_lower", "bb_middle", "cdl_engulfing",
                         "cdl_harami", "cdl_hammer", "atr_14"],
    details={
        "entry_long": "low < BB lower AND bullish candle pattern (engulfing, harami, or hammer)",
        "entry_short": "N/A (long only)",
        "exit": "BB middle touch OR time stop 20 OR stop 2*ATR",
        "indicators": ["BBANDS(20,2,2)", "CDL_ENGULFING", "CDL_HARAMI", "CDL_HAMMER", "ATR(14)"],
        "tags": ["mean_reversion", "pattern", "long_only", "swing"],
    },
)
