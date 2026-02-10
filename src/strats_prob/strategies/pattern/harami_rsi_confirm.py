"""Strategy 89: Harami + RSI Confirm.

Entry Long: cdl_harami > 0 AND RSI < 45 AND RSI rising 2 bars.
Entry Short: cdl_harami < 0 AND RSI > 55 AND RSI falling 2 bars.
Exit: RSI 50 or time 25 or stop 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    below,
    candle_bullish,
    candle_bearish,
    crosses_above,
    crosses_below,
    rising,
    falling,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=89,
    name="harami_rsi_confirm",
    display_name="Harami + RSI Confirm",
    philosophy="A harami pattern confirmed by RSI momentum shift signals "
               "a potential reversal with indicator backing.",
    category="pattern",
    tags=["pattern", "mean_reversion", "long_short", "pattern", "time",
          "CDLHARAMI", "RSI", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        candle_bullish("cdl_harami"),
        below("rsi_14", 45),
        rising("rsi_14", 2),
    ],
    entry_short=[
        candle_bearish("cdl_harami"),
        above("rsi_14", 55),
        falling("rsi_14", 2),
    ],
    exit_long=[
        above("rsi_14", 50),
    ],
    exit_short=[
        below("rsi_14", 50),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=25,
    required_indicators=["cdl_harami", "rsi_14", "atr_14"],
    details={
        "entry_long": "Harami bullish AND RSI < 45 AND RSI rising 2 bars",
        "entry_short": "Harami bearish AND RSI > 55 AND RSI falling 2 bars",
        "exit": "RSI reaches 50 OR time stop 25 bars OR stop 2*ATR",
        "indicators": ["CDL_HARAMI", "RSI(14)", "ATR(14)"],
        "tags": ["pattern", "mean_reversion", "long_short", "swing"],
    },
)
