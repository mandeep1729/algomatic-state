"""Strategy 49: Slow MA Mean Reversion (to SMA50).

Entry Long: close < SMA50 - 2*ATR AND RSI < 40.
Entry Short: close > SMA50 + 2*ATR AND RSI > 60.
Exit: SMA50 touch OR time 30 OR stop 2.5*ATR.
"""

from src.strats_prob.conditions import (
    above,
    below,
    crosses_above,
    crosses_below,
    deviation_from,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=49,
    name="slow_ma_reversion",
    display_name="Slow MA Mean Reversion (SMA50)",
    philosophy="Large deviations from SMA50 are unsustainable; price gravitates back to the slow average.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "threshold", "time",
          "SMA", "RSI", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        deviation_from("close", "sma_50", atr_mult=2.0, direction="below"),
        below("rsi_14", 40),
    ],
    entry_short=[
        deviation_from("close", "sma_50", atr_mult=2.0, direction="above"),
        above("rsi_14", 60),
    ],
    exit_long=[
        crosses_above("close", "sma_50"),
    ],
    exit_short=[
        crosses_below("close", "sma_50"),
    ],
    atr_stop_mult=2.5,
    time_stop_bars=30,
    required_indicators=["close", "sma_50", "rsi_14", "atr_14"],
    details={
        "entry_long": "close < SMA50 - 2*ATR AND RSI < 40",
        "entry_short": "close > SMA50 + 2*ATR AND RSI > 60",
        "exit": "SMA50 touch OR time stop 30 OR stop 2.5*ATR",
        "indicators": ["SMA(50)", "RSI(14)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "threshold", "swing"],
    },
)
