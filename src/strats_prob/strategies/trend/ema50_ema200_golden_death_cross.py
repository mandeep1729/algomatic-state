"""Strategy 2: EMA50/EMA200 Golden/Death Cross (slow).

Entry: EMA50 crosses EMA200 (up=long, down=short).
Exit: opposite cross OR stop=2.5*ATR, optional time stop 120 bars.
"""

from src.strats_prob.conditions import crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=2,
    name="ema50_ema200_golden_death_cross",
    display_name="EMA50/EMA200 Golden/Death Cross",
    philosophy="Slow crossover captures major trend reversals with wide stops.",
    category="trend",
    tags=["trend", "long_short", "cross", "signal", "atr_stop", "EMA", "ATR",
          "trend_favor", "position"],
    direction="long_short",
    entry_long=[
        crosses_above("ema_50", "ema_200"),
    ],
    entry_short=[
        crosses_below("ema_50", "ema_200"),
    ],
    exit_long=[
        crosses_below("ema_50", "ema_200"),
    ],
    exit_short=[
        crosses_above("ema_50", "ema_200"),
    ],
    atr_stop_mult=2.5,
    time_stop_bars=120,
    required_indicators=["ema_50", "ema_200", "atr_14"],
    details={
        "entry_long": "EMA50 crosses above EMA200 (golden cross)",
        "entry_short": "EMA50 crosses below EMA200 (death cross)",
        "exit": "Opposite cross OR stop 2.5*ATR OR time stop 120 bars",
        "indicators": ["EMA(50)", "EMA(200)", "ATR(14)"],
        "tags": ["trend", "long_short", "cross", "position"],
    },
)
