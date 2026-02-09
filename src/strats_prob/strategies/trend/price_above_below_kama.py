"""Strategy 3: Price Above/Below KAMA Trend.

Entry Long: close crosses above KAMA(30).
Entry Short: close crosses below KAMA(30).
Exit: close crosses back OR trail 2*ATR.
"""

from src.strats_prob.conditions import crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=3,
    name="price_above_below_kama",
    display_name="Price Above/Below KAMA Trend",
    philosophy="Adaptive moving average filters noise; price crossing KAMA signals trend change.",
    category="trend",
    tags=["trend", "long_short", "threshold", "trailing", "KAMA", "ATR",
          "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("close", "kama_30"),
    ],
    entry_short=[
        crosses_below("close", "kama_30"),
    ],
    exit_long=[
        crosses_below("close", "kama_30"),
    ],
    exit_short=[
        crosses_above("close", "kama_30"),
    ],
    atr_stop_mult=2.0,
    trailing_atr_mult=2.0,
    required_indicators=["kama_30", "atr_14"],
    details={
        "entry_long": "Close crosses above KAMA(30)",
        "entry_short": "Close crosses below KAMA(30)",
        "exit": "Close crosses back OR trail 2*ATR",
        "indicators": ["KAMA(30)", "ATR(14)"],
        "tags": ["trend", "long_short", "threshold", "swing"],
    },
)
