"""Strategy 72: OBV Trend + Pullback.

Entry Long: OBV above obv_sma_20 AND close > EMA50 AND pullback touches EMA20
            then closes above.
Exit: close < EMA20 OR trail 2*ATR.
"""

from src.strats_prob.conditions import above, below, pullback_to
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=72,
    name="obv_trend_pullback",
    display_name="OBV Trend + Pullback",
    philosophy="Volume flow confirming trend plus a pullback entry improves timing.",
    category="volume_flow",
    tags=["volume_flow", "trend", "long_only", "pullback", "trailing",
          "OBV", "EMA", "ATR", "trend_favor", "swing"],
    direction="long_only",
    entry_long=[
        above("obv", "obv_sma_20"),
        above("close", "ema_50"),
        pullback_to("ema_20"),
    ],
    entry_short=[],
    exit_long=[
        below("close", "ema_20"),
    ],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["obv", "obv_sma_20", "ema_20", "ema_50", "atr_14"],
    details={
        "entry_long": "OBV above its SMA20 AND close > EMA50 AND pullback to EMA20 then close above",
        "exit": "Close < EMA20 OR trailing stop 2*ATR",
        "indicators": ["OBV", "SMA(OBV,20)", "EMA(20)", "EMA(50)", "ATR(14)"],
        "tags": ["volume_flow", "trend", "long_only", "pullback", "swing"],
    },
)
