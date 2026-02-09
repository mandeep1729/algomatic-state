"""Strategy 77: Chaikin A/D Line Trend (proxy via ADOSC).

Entry Long: ADOSC above 0 for 5 bars AND close > EMA50.
Entry Short: ADOSC below 0 for 5 bars AND close < EMA50.
Exit: ADOSC flips sign OR trail 2*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_below, crosses_above, held_for_n_bars
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=77,
    name="chaikin_ad_trend",
    display_name="Chaikin A/D Line Trend",
    philosophy="Sustained accumulation/distribution flow aligned with price trend "
               "indicates strong institutional conviction.",
    category="volume_flow",
    tags=["volume_flow", "trend", "long_short", "threshold", "trailing",
          "ADOSC", "EMA", "ATR", "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        held_for_n_bars("adosc", lambda v: v > 0, 5),
        above("close", "ema_50"),
    ],
    entry_short=[
        held_for_n_bars("adosc", lambda v: v < 0, 5),
        below("close", "ema_50"),
    ],
    exit_long=[
        crosses_below("adosc", 0),
    ],
    exit_short=[
        crosses_above("adosc", 0),
    ],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["adosc", "ema_50", "atr_14"],
    details={
        "entry_long": "ADOSC above 0 for 5 bars AND close > EMA50",
        "entry_short": "ADOSC below 0 for 5 bars AND close < EMA50",
        "exit": "ADOSC flips sign OR trailing stop 2*ATR",
        "indicators": ["ADOSC(3,10)", "EMA(50)", "ATR(14)"],
        "tags": ["volume_flow", "trend", "long_short", "threshold", "swing"],
    },
)
