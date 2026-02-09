"""Strategy 58: Volatility Step-Up + Break.

Setup: ATR(14) rising 5 bars AND BB width rising.
Entry: close breaks donchian_high_10 (long) / donchian_low_10 (short).
Exit: trail 2*ATR.
"""

from src.strats_prob.conditions import breaks_above_level, breaks_below_level, rising
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=58,
    name="vol_stepup_break",
    display_name="Volatility Step-Up + Break",
    philosophy="Rising ATR and BB width confirm volatility expansion before breakout.",
    category="breakout",
    tags=["volatility", "breakout", "long_short", "breakout", "atr_stop",
          "ATR", "BBANDS", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        rising("atr_14", 5),
        rising("bb_width", 5),
        breaks_above_level("donchian_high_10"),
    ],
    entry_short=[
        rising("atr_14", 5),
        rising("bb_width", 5),
        breaks_below_level("donchian_low_10"),
    ],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["atr_14", "bb_width", "donchian_high_10", "donchian_low_10"],
    details={
        "entry_long": "ATR rising 5 bars AND BB width rising AND close breaks 10-bar high",
        "entry_short": "ATR rising 5 bars AND BB width rising AND close breaks 10-bar low",
        "exit": "Trail 2*ATR",
        "indicators": ["ATR(14)", "BBANDS(20,2,2)", "Donchian(10)"],
        "tags": ["volatility", "breakout", "long_short", "swing"],
    },
)
