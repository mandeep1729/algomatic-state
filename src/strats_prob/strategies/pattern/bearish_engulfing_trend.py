"""Strategy 82: Bearish Engulfing + Trend Filter.

Entry Short: cdl_engulfing < 0 AND close < EMA50.
Exit: target 3*ATR OR close > EMA20 OR stop 2*ATR.
"""

from src.strats_prob.conditions import above, below, candle_bearish
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=82,
    name="bearish_engulfing_trend",
    display_name="Bearish Engulfing + Trend Filter",
    philosophy="A bearish engulfing pattern in a downtrend signals strong supply "
               "overwhelming recent demand.",
    category="pattern",
    tags=["pattern", "trend", "short_only", "pattern", "atr_stop", "atr_target",
          "CDLENGULFING", "EMA", "ATR", "trend_favor", "swing"],
    direction="short_only",
    entry_long=[],
    entry_short=[
        candle_bearish("cdl_engulfing"),
        below("close", "ema_50"),
    ],
    exit_long=[],
    exit_short=[
        above("close", "ema_20"),
    ],
    atr_stop_mult=2.0,
    atr_target_mult=3.0,
    required_indicators=["cdl_engulfing", "ema_20", "ema_50", "atr_14"],
    details={
        "entry_short": "Bearish engulfing pattern AND close < EMA50",
        "exit": "Target 3*ATR OR close > EMA20 OR stop 2*ATR",
        "indicators": ["CDL_ENGULFING", "EMA(20)", "EMA(50)", "ATR(14)"],
        "tags": ["pattern", "trend", "short_only", "swing"],
    },
)
