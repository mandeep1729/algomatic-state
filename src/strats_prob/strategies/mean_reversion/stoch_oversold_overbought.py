"""Strategy 30: Stoch Oversold/Overbought Cross.

Entry Long: slowK crosses above slowD while both < 20.
Entry Short: slowK crosses below slowD while both > 80.
Exit: slowK reaches 50 OR time stop 10 OR stop 1.5*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=30,
    name="stoch_oversold_overbought",
    display_name="Stoch Oversold/Overbought Cross",
    philosophy="Stochastic crossovers at extreme zones signal short-term exhaustion and reversion.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "cross", "signal", "time",
          "STOCH", "ATR", "range_favor", "scalp"],
    direction="long_short",
    entry_long=[
        crosses_above("stoch_k", "stoch_d"),
        below("stoch_k", 20),
        below("stoch_d", 20),
    ],
    entry_short=[
        crosses_below("stoch_k", "stoch_d"),
        above("stoch_k", 80),
        above("stoch_d", 80),
    ],
    exit_long=[
        above("stoch_k", 50),
    ],
    exit_short=[
        below("stoch_k", 50),
    ],
    atr_stop_mult=1.5,
    time_stop_bars=10,
    required_indicators=["stoch_k", "stoch_d", "atr_14"],
    details={
        "entry_long": "slowK crosses above slowD while both < 20",
        "entry_short": "slowK crosses below slowD while both > 80",
        "exit": "slowK reaches 50 OR time stop 10 OR stop 1.5*ATR",
        "indicators": ["STOCH(14,3,3)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "cross", "scalp"],
    },
)
