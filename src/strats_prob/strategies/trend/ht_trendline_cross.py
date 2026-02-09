"""Strategy 24: HT Trendline Cross (Hilbert).

Entry: close crosses above HT_TRENDLINE (long) / below (short).
Exit: opposite cross OR stop 2*ATR.
"""

from src.strats_prob.conditions import crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=24,
    name="ht_trendline_cross",
    display_name="HT Trendline Cross (Hilbert)",
    philosophy="Hilbert Transform trendline adapts to dominant cycle; cross signals trend change.",
    category="trend",
    tags=["trend", "long_short", "cross", "signal", "atr_stop", "HT_TRENDLINE",
          "ATR", "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("close", "ht_trendline"),
    ],
    entry_short=[
        crosses_below("close", "ht_trendline"),
    ],
    exit_long=[
        crosses_below("close", "ht_trendline"),
    ],
    exit_short=[
        crosses_above("close", "ht_trendline"),
    ],
    atr_stop_mult=2.0,
    required_indicators=["ht_trendline", "atr_14"],
    details={
        "entry_long": "Close crosses above HT_TRENDLINE",
        "entry_short": "Close crosses below HT_TRENDLINE",
        "exit": "Opposite cross OR stop 2*ATR",
        "indicators": ["HT_TRENDLINE", "ATR(14)"],
        "tags": ["trend", "long_short", "cross", "swing"],
    },
)
