"""Strategy 35: Price vs EMA Deviation Reversion.

Entry Long: (EMA20 - close) > 2*ATR.
Entry Short: (close - EMA20) > 2*ATR.
Exit: close returns to EMA20 OR target 2*ATR; stop 2*ATR.
"""

from src.strats_prob.conditions import crosses_above, crosses_below, deviation_from
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=35,
    name="price_ema_deviation",
    display_name="Price vs EMA Deviation Reversion",
    philosophy="Large deviations from EMA20 are unsustainable; price tends to snap back.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "threshold", "atr_stop", "atr_target",
          "EMA", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        deviation_from("close", "ema_20", atr_mult=2.0, direction="below"),
    ],
    entry_short=[
        deviation_from("close", "ema_20", atr_mult=2.0, direction="above"),
    ],
    exit_long=[
        crosses_above("close", "ema_20"),
    ],
    exit_short=[
        crosses_below("close", "ema_20"),
    ],
    atr_stop_mult=2.0,
    atr_target_mult=2.0,
    required_indicators=["close", "ema_20", "atr_14"],
    details={
        "entry_long": "(EMA20 - close) > 2*ATR (price far below EMA)",
        "entry_short": "(close - EMA20) > 2*ATR (price far above EMA)",
        "exit": "Close returns to EMA20 OR target 2*ATR; stop 2*ATR",
        "indicators": ["EMA(20)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "threshold", "swing"],
    },
)
