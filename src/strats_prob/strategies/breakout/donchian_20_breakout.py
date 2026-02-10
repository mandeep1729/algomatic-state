"""Strategy 51: Donchian 20 High/Low Breakout.

Entry Long: close > donchian_high_20.
Entry Short: close < donchian_low_20.
Exit: trailing stop 2*ATR OR opposite breakout; optional target 4*ATR.
"""

from src.strats_prob.conditions import breaks_above_level, breaks_below_level
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=51,
    name="donchian_20_breakout",
    display_name="Donchian 20 High/Low Breakout",
    philosophy="Classic channel breakout captures new highs/lows as trend initiators.",
    category="breakout",
    tags=["breakout", "long_short", "breakout", "atr_stop", "atr_target",
          "MAX", "MIN", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        breaks_above_level("donchian_high_20"),
    ],
    entry_short=[
        breaks_below_level("donchian_low_20"),
    ],
    exit_long=[
        breaks_below_level("donchian_low_20"),
    ],
    exit_short=[
        breaks_above_level("donchian_high_20"),
    ],
    atr_stop_mult=2.0,
    atr_target_mult=4.0,
    trailing_atr_mult=2.0,
    required_indicators=["donchian_high_20", "donchian_low_20", "atr_14"],
    details={
        "entry_long": "Close breaks above 20-bar Donchian high",
        "entry_short": "Close breaks below 20-bar Donchian low",
        "exit": "Trailing stop 2*ATR OR opposite breakout; target 4*ATR",
        "indicators": ["Donchian(20)", "ATR(14)"],
        "tags": ["breakout", "long_short", "swing"],
    },
)
