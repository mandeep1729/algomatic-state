"""Strategy 80: Price Breakout + Positive Accumulation (ADOSC rising).

Entry Long: close breaks donchian_high_20 AND ADOSC rising 3 bars.
Exit: trail 2*ATR.
"""

from src.strats_prob.conditions import breaks_above_level, rising
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=80,
    name="price_breakout_accumulation",
    display_name="Price Breakout + Positive Accumulation",
    philosophy="Price breakouts backed by rising accumulation/distribution flow "
               "have stronger follow-through.",
    category="volume_flow",
    tags=["volume_flow", "breakout", "long_only", "breakout", "atr_stop",
          "ADOSC", "MAX", "ATR", "vol_expand", "swing"],
    direction="long_only",
    entry_long=[
        breaks_above_level("donchian_high_20"),
        rising("adosc", 3),
    ],
    entry_short=[],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["donchian_high_20", "adosc", "atr_14"],
    details={
        "entry_long": "Close breaks 20-bar Donchian high AND ADOSC rising 3 bars",
        "exit": "Trailing stop 2*ATR",
        "indicators": ["Donchian(20)", "ADOSC(3,10)", "ATR(14)"],
        "tags": ["volume_flow", "breakout", "long_only", "swing"],
    },
)
