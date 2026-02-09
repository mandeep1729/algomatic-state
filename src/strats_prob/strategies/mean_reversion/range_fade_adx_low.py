"""Strategy 43: Range Fade with ADX Low.

Entry Long: ADX < 15 AND RSI crosses up through 30.
Entry Short: ADX < 15 AND RSI crosses down through 70.
Exit: RSI to 50 OR time 20 OR stop 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    below,
    crosses_above,
    crosses_below,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=43,
    name="range_fade_adx_low",
    display_name="Range Fade with ADX Low",
    philosophy="Low ADX confirms ranging market; RSI extremes in ranges are reliable reversion signals.",
    category="mean_reversion",
    tags=["mean_reversion", "regime", "long_short", "threshold", "time",
          "ADX", "RSI", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        below("adx_14", 15),
        crosses_above("rsi_14", 30),
    ],
    entry_short=[
        below("adx_14", 15),
        crosses_below("rsi_14", 70),
    ],
    exit_long=[
        above("rsi_14", 50),
    ],
    exit_short=[
        below("rsi_14", 50),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["adx_14", "rsi_14", "atr_14"],
    details={
        "entry_long": "ADX < 15 AND RSI crosses up through 30",
        "entry_short": "ADX < 15 AND RSI crosses down through 70",
        "exit": "RSI reaches 50 OR time stop 20 OR stop 2*ATR",
        "indicators": ["ADX(14)", "RSI(14)", "ATR(14)"],
        "tags": ["mean_reversion", "regime", "long_short", "swing"],
    },
)
