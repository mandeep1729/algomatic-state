"""Strategy 6: ADX Rising Trend Continuation (DI+/-).

Entry Long: PLUS_DI > MINUS_DI AND ADX rising 3 bars AND ADX>20.
Entry Short: MINUS_DI > PLUS_DI AND ADX rising 3 bars AND ADX>20.
Exit: DI crossover OR SAR trail.
"""

from src.strats_prob.conditions import (
    above,
    below,
    crosses_above,
    crosses_below,
    rising,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=6,
    name="adx_rising_di_continuation",
    display_name="ADX Rising Trend Continuation (DI+/-)",
    philosophy="Rising ADX with DI alignment confirms strengthening trend.",
    category="trend",
    tags=["trend", "long_short", "threshold", "signal", "trailing", "ADX",
          "PLUS_DI", "MINUS_DI", "ATR", "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        above("plus_di_14", "minus_di_14"),
        rising("adx_14", 3),
        above("adx_14", 20),
    ],
    entry_short=[
        above("minus_di_14", "plus_di_14"),
        rising("adx_14", 3),
        above("adx_14", 20),
    ],
    exit_long=[
        crosses_above("minus_di_14", "plus_di_14"),
    ],
    exit_short=[
        crosses_above("plus_di_14", "minus_di_14"),
    ],
    atr_stop_mult=2.0,
    trailing_atr_mult=2.0,
    required_indicators=["adx_14", "plus_di_14", "minus_di_14", "psar", "atr_14"],
    details={
        "entry_long": "PLUS_DI > MINUS_DI AND ADX rising 3 bars AND ADX > 20",
        "entry_short": "MINUS_DI > PLUS_DI AND ADX rising 3 bars AND ADX > 20",
        "exit": "DI crossover OR SAR trail",
        "indicators": ["ADX(14)", "PLUS_DI(14)", "MINUS_DI(14)", "SAR", "ATR(14)"],
        "tags": ["trend", "long_short", "threshold", "swing"],
    },
)
