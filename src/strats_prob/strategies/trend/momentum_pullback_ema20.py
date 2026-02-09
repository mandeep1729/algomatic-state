"""Strategy 11: Momentum + Pullback to EMA20.

Entry Long: close>EMA50 AND ADX>20 AND pullback to EMA20
    (low touches/breaches EMA20 then closes back above).
Exit: close<EMA20 OR trail 2*ATR.
"""

from src.strats_prob.conditions import above, below, pullback_to
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=11,
    name="momentum_pullback_ema20",
    display_name="Momentum + Pullback to EMA20",
    philosophy="Enter trending pullbacks at the fast EMA for high-probability continuation.",
    category="trend",
    tags=["trend", "long_only", "pullback", "trailing", "EMA", "ADX", "ATR",
          "trend_favor", "swing"],
    direction="long_only",
    entry_long=[
        above("close", "ema_50"),
        above("adx_14", 20),
        pullback_to("ema_20"),
    ],
    entry_short=[],
    exit_long=[
        below("close", "ema_20"),
    ],
    exit_short=[],
    atr_stop_mult=2.0,
    trailing_atr_mult=2.0,
    required_indicators=["ema_20", "ema_50", "adx_14", "atr_14"],
    details={
        "entry_long": "Close > EMA50 AND ADX > 20 AND pullback to EMA20",
        "entry_short": "N/A (long only)",
        "exit": "Close < EMA20 OR trail 2*ATR",
        "indicators": ["EMA(20)", "EMA(50)", "ADX(14)", "ATR(14)"],
        "tags": ["trend", "long_only", "pullback", "swing"],
    },
)
