"""Strategy 73: ADOSC Momentum.

Entry Long: ADOSC crosses above 0 AND close > EMA50.
Entry Short: ADOSC crosses below 0 AND close < EMA50.
Exit: ADOSC crosses back OR stop 2*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=73,
    name="adosc_momentum",
    display_name="ADOSC Momentum",
    philosophy="Accumulation/distribution oscillator momentum aligned with trend confirms "
               "institutional flow direction.",
    category="volume_flow",
    tags=["volume_flow", "long_short", "threshold", "time",
          "ADOSC", "ATR", "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("adosc", 0),
        above("close", "ema_50"),
    ],
    entry_short=[
        crosses_below("adosc", 0),
        below("close", "ema_50"),
    ],
    exit_long=[
        crosses_below("adosc", 0),
    ],
    exit_short=[
        crosses_above("adosc", 0),
    ],
    atr_stop_mult=2.0,
    required_indicators=["adosc", "ema_50", "atr_14"],
    details={
        "entry_long": "ADOSC crosses above 0 AND close > EMA50",
        "entry_short": "ADOSC crosses below 0 AND close < EMA50",
        "exit": "ADOSC crosses back through 0 OR stop 2*ATR",
        "indicators": ["ADOSC(3,10)", "EMA(50)", "ATR(14)"],
        "tags": ["volume_flow", "long_short", "threshold", "swing"],
    },
)
