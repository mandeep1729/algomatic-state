"""Strategy 40: MACD Divergence (hist).

Entry Long: price lower low but MACD hist higher low AND hist crosses above 0.
Entry Short: price higher high but hist lower high AND crosses below 0.
Exit: opposite hist cross OR time 30 OR stop 2.5*ATR.
"""

from src.strats_prob.conditions import (
    bullish_divergence,
    bearish_divergence,
    crosses_above,
    crosses_below,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=40,
    name="macd_divergence",
    display_name="MACD Divergence",
    philosophy="MACD histogram divergence from price reveals hidden momentum shifts before reversals.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "divergence", "signal", "time",
          "MACD", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        bullish_divergence("macd_hist", lookback=5),
        crosses_above("macd_hist", 0),
    ],
    entry_short=[
        bearish_divergence("macd_hist", lookback=5),
        crosses_below("macd_hist", 0),
    ],
    exit_long=[
        crosses_below("macd_hist", 0),
    ],
    exit_short=[
        crosses_above("macd_hist", 0),
    ],
    atr_stop_mult=2.5,
    time_stop_bars=30,
    required_indicators=["close", "high", "low", "macd_hist", "atr_14"],
    details={
        "entry_long": "Price lower low but MACD hist higher low AND hist crosses above 0",
        "entry_short": "Price higher high but MACD hist lower high AND hist crosses below 0",
        "exit": "Opposite hist cross OR time stop 30 OR stop 2.5*ATR",
        "indicators": ["MACD(12,26,9)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "divergence", "swing"],
    },
)
