"""Strategy 41: Stoch 'Hook' at Extremes.

Entry Long: slowK < 20 AND slowK turns up 2 bars in a row.
Entry Short: slowK > 80 AND turns down 2 bars.
Exit: slowK reaches 50 OR time 10 OR stop 1.5*ATR.
"""

from src.strats_prob.conditions import above, below, rising, falling
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=41,
    name="stoch_hook_extremes",
    display_name="Stoch Hook at Extremes",
    philosophy="Stochastic turning at extremes (hook pattern) signals imminent reversal with momentum confirmation.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "pattern", "time",
          "STOCH", "ATR", "range_favor", "scalp"],
    direction="long_short",
    entry_long=[
        below("stoch_k", 20),
        rising("stoch_k", 2),
    ],
    entry_short=[
        above("stoch_k", 80),
        falling("stoch_k", 2),
    ],
    exit_long=[
        above("stoch_k", 50),
    ],
    exit_short=[
        below("stoch_k", 50),
    ],
    atr_stop_mult=1.5,
    time_stop_bars=10,
    required_indicators=["stoch_k", "atr_14"],
    details={
        "entry_long": "slowK < 20 AND slowK rising 2 bars in a row",
        "entry_short": "slowK > 80 AND slowK falling 2 bars in a row",
        "exit": "slowK reaches 50 OR time stop 10 OR stop 1.5*ATR",
        "indicators": ["STOCH(14,3,3)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "pattern", "scalp"],
    },
)
