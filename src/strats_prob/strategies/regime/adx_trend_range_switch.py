"""Strategy 91: ADX Trend vs Range Switch (meta-strategy).

Regime A (Trend): if ADX > 25 -> use EMA cross signals (long: EMA20 > EMA50).
Regime B (Range): if ADX < 18 -> use BB reversion signals.
Exit: follow selected sub-strategy exit.
"""

from src.strats_prob.conditions import (
    above,
    below,
    crosses_above,
    crosses_below,
    all_of,
    any_of,
)
from src.strats_prob.strategy_def import StrategyDef

# Regime A (Trend): ADX > 25 AND EMA cross
_trend_long = all_of(
    above("adx_14", 25),
    crosses_above("ema_20", "ema_50"),
)

_trend_short = all_of(
    above("adx_14", 25),
    crosses_below("ema_20", "ema_50"),
)

# Regime B (Range): ADX < 18 AND BB reversion
_range_long = all_of(
    below("adx_14", 18),
    crosses_above("close", "bb_lower"),
)

_range_short = all_of(
    below("adx_14", 18),
    crosses_below("close", "bb_upper"),
)

strategy = StrategyDef(
    id=91,
    name="adx_trend_range_switch",
    display_name="ADX Trend vs Range Switch",
    philosophy="Adapting strategy to the current regime (trending vs ranging) "
               "avoids whipsaws inherent in single-mode approaches.",
    category="regime",
    tags=["regime", "multi_filter", "long_short", "threshold", "mixed",
          "ADX", "EMA", "RSI", "BBANDS", "ATR", "swing"],
    direction="long_short",
    entry_long=[
        any_of(_trend_long, _range_long),
    ],
    entry_short=[
        any_of(_trend_short, _range_short),
    ],
    exit_long=[
        any_of(
            crosses_below("ema_20", "ema_50"),  # trend exit
            above("close", "bb_middle"),         # range exit (target middle)
        ),
    ],
    exit_short=[
        any_of(
            crosses_above("ema_20", "ema_50"),
            below("close", "bb_middle"),
        ),
    ],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["adx_14", "ema_20", "ema_50", "bb_upper", "bb_lower",
                         "bb_middle", "atr_14"],
    details={
        "entry_long": "ADX>25: EMA20 crosses above EMA50; ADX<18: close crosses above BB lower",
        "entry_short": "ADX>25: EMA20 crosses below EMA50; ADX<18: close crosses below BB upper",
        "exit": "Trend: opposite EMA cross; Range: BB middle cross; OR trail 2*ATR",
        "indicators": ["ADX(14)", "EMA(20)", "EMA(50)", "BBANDS(20,2,2)", "ATR(14)"],
        "tags": ["regime", "multi_filter", "long_short", "swing"],
    },
)
