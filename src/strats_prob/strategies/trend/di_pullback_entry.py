"""Strategy 21: DI Pullback Entry.

Entry Long: PLUS_DI>MINUS_DI AND ADX>20 AND RSI dips below 45 then crosses back above 50.
Exit: DI crossover OR trail 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    crosses_above,
    was_below_then_crosses_above,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=21,
    name="di_pullback_entry",
    display_name="DI Pullback Entry",
    philosophy="Enter trend pullbacks when RSI resets and DI direction is confirmed.",
    category="trend",
    tags=["trend", "long_only", "pullback", "signal", "trailing", "PLUS_DI",
          "MINUS_DI", "ADX", "ATR", "trend_favor", "swing"],
    direction="long_only",
    entry_long=[
        above("plus_di_14", "minus_di_14"),
        above("adx_14", 20),
        was_below_then_crosses_above("rsi_14", 50, lookback=5),
    ],
    entry_short=[],
    exit_long=[
        crosses_above("minus_di_14", "plus_di_14"),
    ],
    exit_short=[],
    atr_stop_mult=2.0,
    trailing_atr_mult=2.0,
    required_indicators=["plus_di_14", "minus_di_14", "adx_14", "rsi_14", "atr_14"],
    details={
        "entry_long": "PLUS_DI > MINUS_DI AND ADX > 20 AND RSI dips below 45 then crosses above 50",
        "entry_short": "N/A (long only)",
        "exit": "DI crossover OR trail 2*ATR",
        "indicators": ["PLUS_DI(14)", "MINUS_DI(14)", "ADX(14)", "RSI(14)", "ATR(14)"],
        "tags": ["trend", "long_only", "pullback", "swing"],
    },
)
