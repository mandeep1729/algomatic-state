"""Strategy 76: OBV Divergence Reversal.

Entry Long: price lower low vs 10 bars ago, OBV higher low; bullish candle.
Entry Short: price higher high, OBV lower high; bearish candle.
Exit: time 25 OR target 3*ATR OR stop 2.5*ATR.
"""

from src.strats_prob.conditions import (
    bullish_divergence,
    bearish_divergence,
    candle_bullish,
    candle_bearish,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=76,
    name="obv_divergence_reversal",
    display_name="OBV Divergence Reversal",
    philosophy="Volume flow diverging from price signals hidden accumulation/distribution "
               "that often precedes reversals.",
    category="volume_flow",
    tags=["volume_flow", "mean_reversion", "long_short", "divergence", "time",
          "OBV", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        bullish_divergence("obv", lookback=10),
        candle_bullish("cdl_engulfing"),
    ],
    entry_short=[
        bearish_divergence("obv", lookback=10),
        candle_bearish("cdl_engulfing"),
    ],
    exit_long=[],
    exit_short=[],
    atr_stop_mult=2.5,
    atr_target_mult=3.0,
    time_stop_bars=25,
    required_indicators=["obv", "cdl_engulfing", "atr_14"],
    details={
        "entry_long": "Price lower low vs 10 bars ago AND OBV higher low AND bullish candle",
        "entry_short": "Price higher high AND OBV lower high AND bearish candle",
        "exit": "Time stop 25 bars OR target 3*ATR OR stop 2.5*ATR",
        "indicators": ["OBV", "CDL_ENGULFING", "ATR(14)"],
        "tags": ["volume_flow", "mean_reversion", "long_short", "divergence", "swing"],
    },
)
