"""Strategy 93: Trend Quality Filter (ADX + BB width).

Entry Long: ADX > 20 AND BB width rising AND pullback to EMA20 then bullish close.
Exit: close < EMA20 OR trail 2*ATR.
"""

from src.strats_prob.conditions import above, below, rising, pullback_to
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=93,
    name="trend_quality_filter",
    display_name="Trend Quality Filter",
    philosophy="Combining trend strength (ADX), expanding volatility (BB width), "
               "and pullback timing produces higher quality trend entries.",
    category="regime",
    tags=["regime", "trend", "long_only", "pullback", "trailing",
          "ADX", "BBANDS", "EMA", "ATR", "trend_favor", "swing"],
    direction="long_only",
    entry_long=[
        above("adx_14", 20),
        rising("bb_width", 3),
        pullback_to("ema_20"),
    ],
    entry_short=[],
    exit_long=[
        below("close", "ema_20"),
    ],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["adx_14", "bb_width", "ema_20", "atr_14"],
    details={
        "entry_long": "ADX > 20 AND BB width rising 3 bars AND pullback to EMA20 then close above",
        "exit": "Close < EMA20 OR trailing stop 2*ATR",
        "indicators": ["ADX(14)", "BBANDS width", "EMA(20)", "ATR(14)"],
        "tags": ["regime", "trend", "long_only", "pullback", "swing"],
    },
)
