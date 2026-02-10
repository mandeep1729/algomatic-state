"""Strategy 4: MACD Line/Signal Cross with Trend Filter.

Entry Long: MACD crosses above Signal AND ADX>20.
Entry Short: MACD crosses below Signal AND ADX>20.
Exit: opposite MACD cross OR stop 2*ATR.
"""

from src.strats_prob.conditions import above, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=4,
    name="macd_signal_cross_trend_filter",
    display_name="MACD Line/Signal Cross with Trend Filter",
    philosophy="MACD crossover filtered by ADX ensures entries only in trending markets.",
    category="trend",
    tags=["trend", "long_short", "cross", "signal", "atr_stop", "MACD", "ADX",
          "ATR", "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("macd", "macd_signal"),
        above("adx_14", 20),
    ],
    entry_short=[
        crosses_below("macd", "macd_signal"),
        above("adx_14", 20),
    ],
    exit_long=[
        crosses_below("macd", "macd_signal"),
    ],
    exit_short=[
        crosses_above("macd", "macd_signal"),
    ],
    atr_stop_mult=2.0,
    required_indicators=["macd", "macd_signal", "adx_14", "atr_14"],
    details={
        "entry_long": "MACD crosses above Signal AND ADX > 20",
        "entry_short": "MACD crosses below Signal AND ADX > 20",
        "exit": "Opposite MACD cross OR stop 2*ATR",
        "indicators": ["MACD(12,26,9)", "ADX(14)", "ATR(14)"],
        "tags": ["trend", "long_short", "cross", "swing"],
    },
)
