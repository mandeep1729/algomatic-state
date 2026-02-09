"""Strategy 15: Aroon Trend Start.

Entry Long: AroonUp(25) crosses above 70 AND AroonDown<30.
Entry Short: AroonDown crosses above 70 AND AroonUp<30.
Exit: opposite condition OR stop 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    below,
    crosses_above,
    crosses_below,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=15,
    name="aroon_trend_start",
    display_name="Aroon Trend Start",
    philosophy="Aroon oscillator detects new trend initiation when one direction dominates.",
    category="trend",
    tags=["trend", "long_short", "threshold", "signal", "atr_stop", "AROON",
          "ATR", "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("aroon_up_25", 70),
        below("aroon_down_25", 30),
    ],
    entry_short=[
        crosses_above("aroon_down_25", 70),
        below("aroon_up_25", 30),
    ],
    exit_long=[
        crosses_above("aroon_down_25", 70),
    ],
    exit_short=[
        crosses_above("aroon_up_25", 70),
    ],
    atr_stop_mult=2.0,
    required_indicators=["aroon_up_25", "aroon_down_25", "atr_14"],
    details={
        "entry_long": "AroonUp(25) crosses above 70 AND AroonDown < 30",
        "entry_short": "AroonDown(25) crosses above 70 AND AroonUp < 30",
        "exit": "Opposite Aroon condition OR stop 2*ATR",
        "indicators": ["AROON(25)", "ATR(14)"],
        "tags": ["trend", "long_short", "threshold", "swing"],
    },
)
