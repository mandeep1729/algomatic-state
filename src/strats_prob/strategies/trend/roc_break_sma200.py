"""Strategy 10: ROC Break in Direction of SMA200.

Entry Long: close>SMA200 AND ROC(10) crosses above 0.
Entry Short: close<SMA200 AND ROC crosses below 0.
Exit: ROC back through 0 OR time stop 30 bars OR stop 2*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=10,
    name="roc_break_sma200",
    display_name="ROC Break in Direction of SMA200",
    philosophy="Rate of Change zero-line break confirmed by long-term trend direction.",
    category="trend",
    tags=["trend", "long_short", "threshold", "atr_stop", "time", "ROC", "SMA",
          "ATR", "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        above("close", "sma_200"),
        crosses_above("roc_10", 0),
    ],
    entry_short=[
        below("close", "sma_200"),
        crosses_below("roc_10", 0),
    ],
    exit_long=[
        crosses_below("roc_10", 0),
    ],
    exit_short=[
        crosses_above("roc_10", 0),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=30,
    required_indicators=["roc_10", "sma_200", "atr_14"],
    details={
        "entry_long": "Close > SMA200 AND ROC(10) crosses above 0",
        "entry_short": "Close < SMA200 AND ROC(10) crosses below 0",
        "exit": "ROC back through 0 OR time stop 30 bars OR stop 2*ATR",
        "indicators": ["ROC(10)", "SMA(200)", "ATR(14)"],
        "tags": ["trend", "long_short", "threshold", "swing"],
    },
)
