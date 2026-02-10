"""Strategy 9: APO Momentum Cross (EMA fast-slow).

Entry Long: APO(12,26) crosses above 0 AND close>EMA50.
Entry Short: APO crosses below 0 AND close<EMA50.
Exit: APO crosses back OR stop 2*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=9,
    name="apo_momentum_cross",
    display_name="APO Momentum Cross",
    philosophy="Absolute Price Oscillator zero-line cross with EMA trend filter.",
    category="trend",
    tags=["trend", "long_short", "cross", "signal", "atr_stop", "APO", "ATR",
          "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("apo", 0),
        above("close", "ema_50"),
    ],
    entry_short=[
        crosses_below("apo", 0),
        below("close", "ema_50"),
    ],
    exit_long=[
        crosses_below("apo", 0),
    ],
    exit_short=[
        crosses_above("apo", 0),
    ],
    atr_stop_mult=2.0,
    required_indicators=["apo", "ema_50", "atr_14"],
    details={
        "entry_long": "APO(12,26) crosses above 0 AND close > EMA50",
        "entry_short": "APO crosses below 0 AND close < EMA50",
        "exit": "APO crosses back through 0 OR stop 2*ATR",
        "indicators": ["APO(12,26)", "EMA(50)", "ATR(14)"],
        "tags": ["trend", "long_short", "cross", "swing"],
    },
)
