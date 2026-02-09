"""Strategy 68: 1-2-3 Breakout.

Entry Long: close breaks donchian_high_10 (simplified proxy for pullback high break).
Exit: stop 2*ATR, target 3*ATR.
"""

from src.strats_prob.conditions import breaks_above_level
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=68,
    name="one_two_three_breakout",
    display_name="1-2-3 Breakout",
    philosophy="Simplified swing structure break: break of a short-term high confirms reversal.",
    category="breakout",
    tags=["breakout", "long_only", "breakout", "atr_stop", "atr_target",
          "MAX", "MIN", "ATR", "vol_expand", "swing"],
    direction="long_only",
    entry_long=[
        breaks_above_level("donchian_high_10"),
    ],
    entry_short=[],
    exit_long=[],
    exit_short=[],
    atr_stop_mult=2.0,
    atr_target_mult=3.0,
    required_indicators=["donchian_high_10", "atr_14"],
    details={
        "entry_long": "Close breaks above 10-bar Donchian high (pullback high proxy)",
        "entry_short": "N/A (long only)",
        "exit": "Stop 2*ATR, target 3*ATR",
        "indicators": ["Donchian(10)", "ATR(14)"],
        "tags": ["breakout", "long_only", "swing"],
    },
)
