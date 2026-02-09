"""Strategy 98: Trend + Mean Reversion 'Add-on' (simplified).

Base Entry: EMA20 crosses above EMA50 (long).
Simplified: just uses the base entry without pyramiding since the probe engine
does not support multiple simultaneous lots.
Exit: close < EMA50 OR trail 2*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=98,
    name="trend_mr_addon",
    display_name="Trend + Mean Reversion Add-on",
    philosophy="Entering on a trend signal and using mean reversion pullbacks for "
               "add-ons (simplified to single entry) combines trend-following "
               "with better timing.",
    category="regime",
    tags=["trend", "mean_reversion", "multi_filter", "long_only", "pullback",
          "trailing", "EMA", "RSI", "ATR", "trend_favor", "position"],
    direction="long_only",
    entry_long=[
        crosses_above("ema_20", "ema_50"),
        above("close", "ema_50"),
    ],
    entry_short=[],
    exit_long=[
        below("close", "ema_50"),
    ],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["ema_20", "ema_50", "atr_14"],
    details={
        "entry_long": "EMA20 crosses above EMA50 AND close > EMA50",
        "exit": "Close < EMA50 OR trailing stop 2*ATR",
        "indicators": ["EMA(20)", "EMA(50)", "ATR(14)"],
        "tags": ["trend", "mean_reversion", "multi_filter", "long_only", "position"],
    },
)
