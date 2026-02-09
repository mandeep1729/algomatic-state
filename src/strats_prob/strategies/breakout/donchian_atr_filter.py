"""Strategy 52: Donchian + ATR Filter.

Entry: as #51 AND (high-low) > 1.2*ATR today.
Exit: trail 2*ATR.
"""

from src.strats_prob.conditions import (
    breaks_above_level,
    breaks_below_level,
    range_exceeds_atr,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=52,
    name="donchian_atr_filter",
    display_name="Donchian + ATR Filter",
    philosophy="Donchian breakout filtered by range expansion to avoid false breaks.",
    category="breakout",
    tags=["breakout", "volatility", "long_short", "breakout", "atr_stop",
          "MAX", "MIN", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        breaks_above_level("donchian_high_20"),
        range_exceeds_atr(1.2),
    ],
    entry_short=[
        breaks_below_level("donchian_low_20"),
        range_exceeds_atr(1.2),
    ],
    exit_long=[
        breaks_below_level("donchian_low_20"),
    ],
    exit_short=[
        breaks_above_level("donchian_high_20"),
    ],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["donchian_high_20", "donchian_low_20", "atr_14",
                         "high", "low"],
    details={
        "entry_long": "Close breaks 20-bar Donchian high AND bar range > 1.2*ATR",
        "entry_short": "Close breaks 20-bar Donchian low AND bar range > 1.2*ATR",
        "exit": "Trail 2*ATR",
        "indicators": ["Donchian(20)", "ATR(14)"],
        "tags": ["breakout", "volatility", "long_short", "swing"],
    },
)
