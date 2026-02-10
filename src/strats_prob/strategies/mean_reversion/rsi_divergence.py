"""Strategy 39: RSI Divergence (simple).

Entry Long: price makes lower low vs 5 bars ago AND RSI makes higher low AND RSI < 40.
Entry Short: price makes higher high AND RSI makes lower high AND RSI > 60.
Exit: RSI crosses 50 OR time 25 OR stop 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    below,
    bullish_divergence,
    bearish_divergence,
    crosses_above,
    crosses_below,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=39,
    name="rsi_divergence",
    display_name="RSI Divergence",
    philosophy="Price-RSI divergence reveals waning momentum; reversion follows as trend exhausts.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "divergence", "signal", "time",
          "RSI", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        bullish_divergence("rsi_14", lookback=5),
        below("rsi_14", 40),
    ],
    entry_short=[
        bearish_divergence("rsi_14", lookback=5),
        above("rsi_14", 60),
    ],
    exit_long=[
        crosses_above("rsi_14", 50),
    ],
    exit_short=[
        crosses_below("rsi_14", 50),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=25,
    required_indicators=["close", "high", "low", "rsi_14", "atr_14"],
    details={
        "entry_long": "Price lower low vs 5 bars ago AND RSI higher low AND RSI < 40",
        "entry_short": "Price higher high AND RSI lower high AND RSI > 60",
        "exit": "RSI crosses 50 OR time stop 25 OR stop 2*ATR",
        "indicators": ["RSI(14)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "divergence", "swing"],
    },
)
