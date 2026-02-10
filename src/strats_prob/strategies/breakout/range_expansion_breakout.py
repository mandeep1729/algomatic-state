"""Strategy 56: Range Expansion Day Breakout (RED).

Entry Long: today's range > 1.8*ATR AND close in top 20% of range.
Entry Short: range > 1.8*ATR AND close in bottom 20%.
Exit: time stop 5-10 bars OR trail 1.5*ATR.
"""

from src.strats_prob.conditions import (
    in_bottom_pct_of_range,
    in_top_pct_of_range,
    range_exceeds_atr,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=56,
    name="range_expansion_breakout",
    display_name="Range Expansion Day Breakout",
    philosophy="Wide-range bars with directional closes signal strong intraday conviction.",
    category="breakout",
    tags=["breakout", "volatility", "long_short", "breakout", "time",
          "atr_stop", "ATR", "vol_expand", "scalp"],
    direction="long_short",
    entry_long=[
        range_exceeds_atr(1.8),
        in_top_pct_of_range(0.20),
    ],
    entry_short=[
        range_exceeds_atr(1.8),
        in_bottom_pct_of_range(0.20),
    ],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=1.5,
    atr_stop_mult=1.5,
    time_stop_bars=8,
    required_indicators=["atr_14", "high", "low", "close"],
    details={
        "entry_long": "Bar range > 1.8*ATR AND close in top 20% of range",
        "entry_short": "Bar range > 1.8*ATR AND close in bottom 20% of range",
        "exit": "Time stop 8 bars OR trail 1.5*ATR",
        "indicators": ["ATR(14)"],
        "tags": ["breakout", "volatility", "long_short", "scalp"],
    },
)
