"""Strategy 71: OBV Breakout Confirmation.

Entry Long: close breaks donchian_high_20 AND OBV breaks obv_high_20.
Entry Short: close breaks donchian_low_20 AND OBV breaks obv_low_20.
Exit: trail 2*ATR.
"""

from src.strats_prob.conditions import breaks_above_level, breaks_below_level
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=71,
    name="obv_breakout_confirmation",
    display_name="OBV Breakout Confirmation",
    philosophy="Price breakouts confirmed by volume flow (OBV) breakouts have higher conviction.",
    category="volume_flow",
    tags=["volume_flow", "breakout", "long_short", "breakout", "atr_stop",
          "OBV", "MAX", "MIN", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        breaks_above_level("donchian_high_20"),
        breaks_above_level("obv_high_20"),
    ],
    entry_short=[
        breaks_below_level("donchian_low_20"),
        breaks_below_level("obv_low_20"),
    ],
    exit_long=[
        breaks_below_level("donchian_low_20"),
    ],
    exit_short=[
        breaks_above_level("donchian_high_20"),
    ],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["donchian_high_20", "donchian_low_20", "obv",
                         "obv_high_20", "obv_low_20", "atr_14"],
    details={
        "entry_long": "Close breaks 20-bar Donchian high AND OBV breaks 20-bar OBV high",
        "entry_short": "Close breaks 20-bar Donchian low AND OBV breaks 20-bar OBV low",
        "exit": "Trailing stop 2*ATR",
        "indicators": ["Donchian(20)", "OBV", "ATR(14)"],
        "tags": ["volume_flow", "breakout", "long_short", "swing"],
    },
)
