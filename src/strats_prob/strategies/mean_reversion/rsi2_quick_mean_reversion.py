"""Strategy 34: RSI(2) Quick Mean Reversion.

Entry Long: RSI(2) < 5 AND close above SMA50.
Entry Short: RSI(2) > 95 AND close below SMA50.
Exit: RSI(2) > 60 (long) / < 40 (short) OR time stop 5 OR stop 1*ATR.
"""

from src.strats_prob.conditions import above, below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=34,
    name="rsi2_quick_mean_reversion",
    display_name="RSI(2) Quick Mean Reversion",
    philosophy="Ultra-short RSI(2) extremes capture quick snapback moves with tight risk.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "threshold", "time",
          "RSI", "SMA", "ATR", "range_favor", "scalp", "tight"],
    direction="long_short",
    entry_long=[
        below("rsi_2", 5),
        above("close", "sma_50"),
    ],
    entry_short=[
        above("rsi_2", 95),
        below("close", "sma_50"),
    ],
    exit_long=[
        above("rsi_2", 60),
    ],
    exit_short=[
        below("rsi_2", 40),
    ],
    atr_stop_mult=1.0,
    time_stop_bars=5,
    required_indicators=["rsi_2", "close", "sma_50", "atr_14"],
    details={
        "entry_long": "RSI(2) < 5 AND close > SMA50",
        "entry_short": "RSI(2) > 95 AND close < SMA50",
        "exit": "RSI(2) > 60 (long) / < 40 (short) OR time stop 5 OR stop 1*ATR",
        "indicators": ["RSI(2)", "SMA(50)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "threshold", "scalp", "tight"],
    },
)
