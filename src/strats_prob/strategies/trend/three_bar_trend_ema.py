"""Strategy 25: Three-Bar Trend with EMA Filter.

Entry Long: close>EMA50 AND last 3 closes increasing.
Entry Short: close<EMA50 AND last 3 closes decreasing.
Exit: opposite 2 closes OR time stop 8 bars OR stop 1.5*ATR.
"""

from src.strats_prob.conditions import (
    above,
    below,
    consecutive_higher_closes,
    consecutive_lower_closes,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=25,
    name="three_bar_trend_ema",
    display_name="Three-Bar Trend with EMA Filter",
    philosophy="Short-term momentum (3 consecutive directional closes) with EMA trend confirmation.",
    category="trend",
    tags=["trend", "long_short", "threshold", "time", "atr_stop", "EMA", "ATR",
          "trend_favor", "scalp"],
    direction="long_short",
    entry_long=[
        above("close", "ema_50"),
        consecutive_higher_closes(3),
    ],
    entry_short=[
        below("close", "ema_50"),
        consecutive_lower_closes(3),
    ],
    exit_long=[
        consecutive_lower_closes(2),
    ],
    exit_short=[
        consecutive_higher_closes(2),
    ],
    atr_stop_mult=1.5,
    time_stop_bars=8,
    required_indicators=["ema_50", "atr_14"],
    details={
        "entry_long": "Close > EMA50 AND last 3 closes increasing",
        "entry_short": "Close < EMA50 AND last 3 closes decreasing",
        "exit": "Opposite 2 closes OR time stop 8 bars OR stop 1.5*ATR",
        "indicators": ["EMA(50)", "ATR(14)"],
        "tags": ["trend", "long_short", "threshold", "scalp"],
    },
)
