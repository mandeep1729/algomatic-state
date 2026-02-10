"""Strategy 18: PPO Signal Cross with Long-Term Filter.

Entry Long: close>SMA200 AND PPO crosses above PPO signal.
Entry Short: close<SMA200 AND PPO crosses below signal.
Exit: opposite cross OR stop 2*ATR.
"""

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=18,
    name="ppo_signal_cross",
    display_name="PPO Signal Cross with Long-Term Filter",
    philosophy="Percentage Price Oscillator normalises MACD; SMA200 filter ensures trend alignment.",
    category="trend",
    tags=["trend", "long_short", "cross", "signal", "atr_stop", "PPO", "SMA",
          "ATR", "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        above("close", "sma_200"),
        crosses_above("ppo", "ppo_signal"),
    ],
    entry_short=[
        below("close", "sma_200"),
        crosses_below("ppo", "ppo_signal"),
    ],
    exit_long=[
        crosses_below("ppo", "ppo_signal"),
    ],
    exit_short=[
        crosses_above("ppo", "ppo_signal"),
    ],
    atr_stop_mult=2.0,
    required_indicators=["ppo", "ppo_signal", "sma_200", "atr_14"],
    details={
        "entry_long": "Close > SMA200 AND PPO crosses above PPO signal",
        "entry_short": "Close < SMA200 AND PPO crosses below PPO signal",
        "exit": "Opposite cross OR stop 2*ATR",
        "indicators": ["PPO", "PPO Signal", "SMA(200)", "ATR(14)"],
        "tags": ["trend", "long_short", "cross", "swing"],
    },
)
