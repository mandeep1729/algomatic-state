"""Strategy 16: Ichimoku-lite (using EMAs as proxy).

Entry Long: EMA20>EMA50>EMA200 AND close>EMA20.
Exit: EMA20<EMA50 OR close<EMA50 OR trail 2*ATR.
"""

from src.strats_prob.conditions import above, any_of, below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=16,
    name="ichimoku_lite",
    display_name="Ichimoku-lite (EMA proxy)",
    philosophy="EMA stack alignment (20>50>200) proxies Ichimoku cloud bullish conditions.",
    category="trend",
    tags=["trend", "long_only", "threshold", "trailing", "EMA", "ATR",
          "trend_favor", "swing"],
    direction="long_only",
    entry_long=[
        above("ema_20", "ema_50"),
        above("ema_50", "ema_200"),
        above("close", "ema_20"),
    ],
    entry_short=[],
    exit_long=[
        any_of(
            below("ema_20", "ema_50"),
            below("close", "ema_50"),
        ),
    ],
    exit_short=[],
    atr_stop_mult=2.0,
    trailing_atr_mult=2.0,
    required_indicators=["ema_20", "ema_50", "ema_200", "atr_14"],
    details={
        "entry_long": "EMA20 > EMA50 > EMA200 AND close > EMA20",
        "entry_short": "N/A (long only)",
        "exit": "EMA20 < EMA50 OR close < EMA50 OR trail 2*ATR",
        "indicators": ["EMA(20)", "EMA(50)", "EMA(200)", "ATR(14)"],
        "tags": ["trend", "long_only", "threshold", "swing"],
    },
)
