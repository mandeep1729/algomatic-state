"""Strategy 62: MACD Breakout Confirmation.

Entry Long: close breaks donchian_high_20 AND MACD>0.
Entry Short: close breaks donchian_low_20 AND MACD<0.
Exit: MACD crosses 0 opposite OR trail 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    below,
    breaks_above_level,
    breaks_below_level,
    crosses_above,
    crosses_below,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=62,
    name="macd_breakout_confirmation",
    display_name="MACD Breakout Confirmation",
    philosophy="MACD momentum confirms Donchian breakout to filter false breakouts.",
    category="breakout",
    tags=["breakout", "long_short", "breakout", "atr_stop",
          "MACD", "MAX", "MIN", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        breaks_above_level("donchian_high_20"),
        above("macd", 0),
    ],
    entry_short=[
        breaks_below_level("donchian_low_20"),
        below("macd", 0),
    ],
    exit_long=[
        crosses_below("macd", 0),
    ],
    exit_short=[
        crosses_above("macd", 0),
    ],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["macd", "donchian_high_20", "donchian_low_20", "atr_14"],
    details={
        "entry_long": "Close breaks 20-bar Donchian high AND MACD > 0",
        "entry_short": "Close breaks 20-bar Donchian low AND MACD < 0",
        "exit": "MACD crosses 0 opposite OR trail 2*ATR",
        "indicators": ["MACD(12,26,9)", "Donchian(20)", "ATR(14)"],
        "tags": ["breakout", "long_short", "swing"],
    },
)
