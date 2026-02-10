"""Strategy 97: Breakout Only When Volume/Flow Confirms.

Entry Long: close breaks donchian_high_20 AND OBV breaks obv_high_20 AND ADOSC > 0.
Entry Short: close breaks donchian_low_20 AND OBV breaks obv_low_20 AND ADOSC < 0.
Exit: trail 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    below,
    breaks_above_level,
    breaks_below_level,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=97,
    name="volume_confirmed_breakout",
    display_name="Breakout Only When Volume/Flow Confirms",
    philosophy="Requiring multiple volume/flow confirmations filters out false "
               "breakouts that lack institutional participation.",
    category="regime",
    tags=["multi_filter", "breakout", "volume_flow", "long_short", "breakout",
          "atr_stop", "MAX", "MIN", "OBV", "ADOSC", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        breaks_above_level("donchian_high_20"),
        breaks_above_level("obv_high_20"),
        above("adosc", 0),
    ],
    entry_short=[
        breaks_below_level("donchian_low_20"),
        breaks_below_level("obv_low_20"),
        below("adosc", 0),
    ],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["donchian_high_20", "donchian_low_20", "obv",
                         "obv_high_20", "obv_low_20", "adosc", "atr_14"],
    details={
        "entry_long": "Close breaks Donchian high AND OBV breaks OBV high AND ADOSC > 0",
        "entry_short": "Close breaks Donchian low AND OBV breaks OBV low AND ADOSC < 0",
        "exit": "Trailing stop 2*ATR",
        "indicators": ["Donchian(20)", "OBV", "ADOSC(3,10)", "ATR(14)"],
        "tags": ["multi_filter", "breakout", "volume_flow", "long_short", "swing"],
    },
)
