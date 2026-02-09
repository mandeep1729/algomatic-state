"""Strategy 22: Trend Continuation After RSI Reset.

Entry Long: close>EMA50 AND RSI(14) falls below 40 then crosses back above 50.
Exit: RSI crosses below 45 OR close<EMA50 OR stop 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    any_of,
    below,
    crosses_below,
    was_below_then_crosses_above,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=22,
    name="trend_continuation_rsi_reset",
    display_name="Trend Continuation After RSI Reset",
    philosophy="RSI dip-and-recover in an uptrend signals exhausted sellers and fresh momentum.",
    category="trend",
    tags=["trend", "long_only", "pullback", "signal", "atr_stop", "RSI", "EMA",
          "ATR", "trend_favor", "swing"],
    direction="long_only",
    entry_long=[
        above("close", "ema_50"),
        was_below_then_crosses_above("rsi_14", 50, lookback=10),
    ],
    entry_short=[],
    exit_long=[
        any_of(
            crosses_below("rsi_14", 45),
            below("close", "ema_50"),
        ),
    ],
    exit_short=[],
    atr_stop_mult=2.0,
    required_indicators=["ema_50", "rsi_14", "atr_14"],
    details={
        "entry_long": "Close > EMA50 AND RSI(14) falls below 40 then crosses above 50",
        "entry_short": "N/A (long only)",
        "exit": "RSI crosses below 45 OR close < EMA50 OR stop 2*ATR",
        "indicators": ["EMA(50)", "RSI(14)", "ATR(14)"],
        "tags": ["trend", "long_only", "pullback", "swing"],
    },
)
