"""Strategy 57: Opening Range Breakout Proxy.

Use donchian_high_10 and donchian_low_10 as proxy for N-bar range.
Entry: break above donchian_high_10 (long) / below donchian_low_10 (short).
Exit: time stop 15 OR trail 1.5*ATR.
"""

from src.strats_prob.conditions import breaks_above_level, breaks_below_level
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=57,
    name="opening_range_breakout",
    display_name="Opening Range Breakout Proxy",
    philosophy="Proxy for opening range breakout using short Donchian channel.",
    category="breakout",
    tags=["breakout", "long_short", "breakout", "time",
          "MAX", "MIN", "ATR", "vol_expand", "scalp"],
    direction="long_short",
    entry_long=[
        breaks_above_level("donchian_high_10"),
    ],
    entry_short=[
        breaks_below_level("donchian_low_10"),
    ],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=1.5,
    atr_stop_mult=1.5,
    time_stop_bars=15,
    required_indicators=["donchian_high_10", "donchian_low_10", "atr_14"],
    details={
        "entry_long": "Close breaks above 10-bar Donchian high",
        "entry_short": "Close breaks below 10-bar Donchian low",
        "exit": "Time stop 15 bars OR trail 1.5*ATR",
        "indicators": ["Donchian(10)", "ATR(14)"],
        "tags": ["breakout", "long_short", "scalp"],
    },
)
