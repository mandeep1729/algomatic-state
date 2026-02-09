"""Strategy 7: SAR Trend Ride.

Entry Long: close crosses above SAR.
Entry Short: close crosses below SAR.
Exit: SAR flip (close crosses opposite). Optional initial stop 2*ATR.
"""

from src.strats_prob.conditions import crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=7,
    name="sar_trend_ride",
    display_name="SAR Trend Ride",
    philosophy="Parabolic SAR provides built-in trailing stop that accelerates with trend.",
    category="trend",
    tags=["trend", "long_short", "threshold", "trailing", "SAR", "ATR",
          "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("close", "psar"),
    ],
    entry_short=[
        crosses_below("close", "psar"),
    ],
    exit_long=[
        crosses_below("close", "psar"),
    ],
    exit_short=[
        crosses_above("close", "psar"),
    ],
    atr_stop_mult=2.0,
    required_indicators=["psar", "atr_14"],
    details={
        "entry_long": "Close crosses above Parabolic SAR",
        "entry_short": "Close crosses below Parabolic SAR",
        "exit": "SAR flip (close crosses opposite) OR stop 2*ATR",
        "indicators": ["SAR(0.02, 0.2)", "ATR(14)"],
        "tags": ["trend", "long_short", "threshold", "swing"],
    },
)
