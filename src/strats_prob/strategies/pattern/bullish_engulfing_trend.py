"""Strategy 81: Bullish Engulfing + Trend Filter.

Entry Long: cdl_engulfing > 0 AND close > EMA50.
Exit: target 3*ATR OR close < EMA20 OR stop 2*ATR.
"""

from src.strats_prob.conditions import above, below, candle_bullish
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=81,
    name="bullish_engulfing_trend",
    display_name="Bullish Engulfing + Trend Filter",
    philosophy="A bullish engulfing pattern in an uptrend signals strong demand "
               "overwhelming recent supply.",
    category="pattern",
    tags=["pattern", "trend", "long_only", "pattern", "atr_stop", "atr_target",
          "CDLENGULFING", "EMA", "ATR", "trend_favor", "swing"],
    direction="long_only",
    entry_long=[
        candle_bullish("cdl_engulfing"),
        above("close", "ema_50"),
    ],
    entry_short=[],
    exit_long=[
        below("close", "ema_20"),
    ],
    exit_short=[],
    atr_stop_mult=2.0,
    atr_target_mult=3.0,
    required_indicators=["cdl_engulfing", "ema_20", "ema_50", "atr_14"],
    details={
        "entry_long": "Bullish engulfing pattern AND close > EMA50",
        "exit": "Target 3*ATR OR close < EMA20 OR stop 2*ATR",
        "indicators": ["CDL_ENGULFING", "EMA(20)", "EMA(50)", "ATR(14)"],
        "tags": ["pattern", "trend", "long_only", "swing"],
    },
)
