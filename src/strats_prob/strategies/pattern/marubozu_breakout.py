"""Strategy 90: Marubozu Breakout Continuation.

Entry Long: cdl_marubozu > 0 AND close breaks donchian_high_10.
Entry Short: cdl_marubozu < 0 AND close breaks donchian_low_10.
Exit: time 20 OR trail 2*ATR.
"""

from src.strats_prob.conditions import (
    candle_bullish,
    candle_bearish,
    breaks_above_level,
    breaks_below_level,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=90,
    name="marubozu_breakout",
    display_name="Marubozu Breakout Continuation",
    philosophy="A strong full-bodied candle breaking a recent price level signals "
               "decisive directional commitment.",
    category="pattern",
    tags=["pattern", "breakout", "long_short", "pattern", "breakout", "time",
          "CDLMARUBOZU", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        candle_bullish("cdl_marubozu"),
        breaks_above_level("donchian_high_10"),
    ],
    entry_short=[
        candle_bearish("cdl_marubozu"),
        breaks_below_level("donchian_low_10"),
    ],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["cdl_marubozu", "donchian_high_10", "donchian_low_10", "atr_14"],
    details={
        "entry_long": "Bullish marubozu AND close breaks 10-bar Donchian high",
        "entry_short": "Bearish marubozu AND close breaks 10-bar Donchian low",
        "exit": "Time stop 20 bars OR trailing stop 2*ATR",
        "indicators": ["CDL_MARUBOZU", "Donchian(10)", "ATR(14)"],
        "tags": ["pattern", "breakout", "long_short", "swing"],
    },
)
