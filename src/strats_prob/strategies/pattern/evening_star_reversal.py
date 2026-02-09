"""Strategy 86: Evening Star (reversal).

Entry Short: cdl_evening_star < 0.
Exit: time 30 OR target 3*ATR OR stop 2.5*ATR.
"""

from src.strats_prob.conditions import candle_bearish
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=86,
    name="evening_star_reversal",
    display_name="Evening Star Reversal",
    philosophy="The evening star three-candle pattern signals a potential topping "
               "reversal as sellers regain control.",
    category="pattern",
    tags=["pattern", "mean_reversion", "short_only", "pattern", "atr_stop",
          "CDLEVENINGSTAR", "ATR", "range_favor", "swing"],
    direction="short_only",
    entry_long=[],
    entry_short=[
        candle_bearish("cdl_evening_star"),
    ],
    exit_long=[],
    exit_short=[],
    atr_stop_mult=2.5,
    atr_target_mult=3.0,
    time_stop_bars=30,
    required_indicators=["cdl_evening_star", "atr_14"],
    details={
        "entry_short": "Evening star pattern detected (cdl_evening_star < 0)",
        "exit": "Time stop 30 bars OR target 3*ATR OR stop 2.5*ATR",
        "indicators": ["CDL_EVENING_STAR", "ATR(14)"],
        "tags": ["pattern", "mean_reversion", "short_only", "swing"],
    },
)
