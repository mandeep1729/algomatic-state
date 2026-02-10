"""Strategy 1: EMA20/EMA50 Trend Cross.

Entry Long: EMA20 crosses above EMA50 AND close > EMA50.
Entry Short: EMA20 crosses below EMA50 AND close < EMA50.
Exit: opposite cross OR trailing stop = 2*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=1,
    name="ema20_ema50_trend_cross",
    display_name="EMA20/EMA50 Trend Cross",
    philosophy="Classic dual-EMA crossover captures medium-term trend shifts.",
    category="trend",
    tags=["trend", "long_short", "cross", "signal", "atr_stop", "EMA", "ATR",
          "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("ema_20", "ema_50"),
        above("close", "ema_50"),
    ],
    entry_short=[
        crosses_below("ema_20", "ema_50"),
        below("close", "ema_50"),
    ],
    exit_long=[
        crosses_below("ema_20", "ema_50"),
    ],
    exit_short=[
        crosses_above("ema_20", "ema_50"),
    ],
    atr_stop_mult=2.0,
    trailing_atr_mult=2.0,
    required_indicators=["ema_20", "ema_50", "atr_14"],
    details={
        "entry_long": "EMA20 crosses above EMA50 AND close > EMA50",
        "entry_short": "EMA20 crosses below EMA50 AND close < EMA50",
        "exit": "Opposite cross OR trailing stop 2*ATR",
        "indicators": ["EMA(20)", "EMA(50)", "ATR(14)"],
        "tags": ["trend", "long_short", "cross", "swing"],
    },
)
