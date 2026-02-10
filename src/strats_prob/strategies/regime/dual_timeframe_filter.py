"""Strategy 95: Dual-Timeframe Filter (proxy with slow MA).

HTF filter proxy: close > SMA200.
LTF entry: RSI crosses above 50 after dip < 40 AND close > EMA20.
Exit: close < EMA20 OR trail 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    below,
    was_below_then_crosses_above,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=95,
    name="dual_timeframe_filter",
    display_name="Dual-Timeframe Filter",
    philosophy="Using a slow MA as a higher-timeframe proxy ensures entries "
               "align with the broader trend, filtering counter-trend setups.",
    category="regime",
    tags=["multi_filter", "trend", "long_only", "pullback", "trailing",
          "EMA", "RSI", "ATR", "trend_favor", "swing"],
    direction="long_only",
    entry_long=[
        above("close", "sma_200"),
        was_below_then_crosses_above("rsi_14", 50, lookback=10),
        above("close", "ema_20"),
    ],
    entry_short=[],
    exit_long=[
        below("close", "ema_20"),
    ],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["sma_200", "rsi_14", "ema_20", "atr_14"],
    details={
        "entry_long": "Close > SMA200 (HTF filter) AND RSI crosses above 50 after dip < 40 AND close > EMA20",
        "exit": "Close < EMA20 OR trailing stop 2*ATR",
        "indicators": ["SMA(200)", "RSI(14)", "EMA(20)", "ATR(14)"],
        "tags": ["multi_filter", "trend", "long_only", "pullback", "swing"],
    },
)
