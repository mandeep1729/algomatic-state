"""Strategy 85: Morning Star (reversal).

Entry Long: cdl_morning_star > 0.
Exit: time 30 OR target 3*ATR OR stop 2.5*ATR.
"""

from src.strats_prob.conditions import candle_bullish
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=85,
    name="morning_star_reversal",
    display_name="Morning Star Reversal",
    philosophy="The morning star three-candle pattern signals a potential bottoming "
               "reversal as buyers regain control.",
    category="pattern",
    tags=["pattern", "mean_reversion", "long_only", "pattern", "atr_stop",
          "CDLMORNINGSTAR", "ATR", "range_favor", "swing"],
    direction="long_only",
    entry_long=[
        candle_bullish("cdl_morning_star"),
    ],
    entry_short=[],
    exit_long=[],
    exit_short=[],
    atr_stop_mult=2.5,
    atr_target_mult=3.0,
    time_stop_bars=30,
    required_indicators=["cdl_morning_star", "atr_14"],
    details={
        "entry_long": "Morning star pattern detected (cdl_morning_star > 0)",
        "exit": "Time stop 30 bars OR target 3*ATR OR stop 2.5*ATR",
        "indicators": ["CDL_MORNING_STAR", "ATR(14)"],
        "tags": ["pattern", "mean_reversion", "long_only", "swing"],
    },
)
