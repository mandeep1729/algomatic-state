"""Strategy 5: MACD Histogram Zero-Line.

Entry Long: MACD hist crosses above 0.
Entry Short: hist crosses below 0.
Exit: hist crosses back OR trail 2*ATR.
"""

from src.strats_prob.conditions import crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=5,
    name="macd_hist_zero_line",
    display_name="MACD Histogram Zero-Line",
    philosophy="Histogram zero-line cross captures momentum shifts earlier than MACD line cross.",
    category="trend",
    tags=["trend", "long_short", "threshold", "trailing", "MACD", "ATR",
          "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("macd_hist", 0),
    ],
    entry_short=[
        crosses_below("macd_hist", 0),
    ],
    exit_long=[
        crosses_below("macd_hist", 0),
    ],
    exit_short=[
        crosses_above("macd_hist", 0),
    ],
    atr_stop_mult=2.0,
    trailing_atr_mult=2.0,
    required_indicators=["macd_hist", "atr_14"],
    details={
        "entry_long": "MACD histogram crosses above 0",
        "entry_short": "MACD histogram crosses below 0",
        "exit": "Histogram crosses back OR trail 2*ATR",
        "indicators": ["MACD(12,26,9)", "ATR(14)"],
        "tags": ["trend", "long_short", "threshold", "swing"],
    },
)
