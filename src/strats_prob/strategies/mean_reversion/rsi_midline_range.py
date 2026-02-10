"""Strategy 46: RSI Midline Range Strategy.

Entry Long: ADX < 20 AND RSI crosses above 50 from below.
Entry Short: ADX < 20 AND RSI crosses below 50 from above.
Exit: RSI crosses back OR time 25 OR stop 2*ATR.
"""

from src.strats_prob.conditions import below, crosses_above, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=46,
    name="rsi_midline_range",
    display_name="RSI Midline Range Strategy",
    philosophy="In ranging markets (low ADX), RSI crossing the midline signals directional micro-shifts.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "cross", "signal", "time",
          "RSI", "ADX", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        below("adx_14", 20),
        crosses_above("rsi_14", 50),
    ],
    entry_short=[
        below("adx_14", 20),
        crosses_below("rsi_14", 50),
    ],
    exit_long=[
        crosses_below("rsi_14", 50),
    ],
    exit_short=[
        crosses_above("rsi_14", 50),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=25,
    required_indicators=["adx_14", "rsi_14", "atr_14"],
    details={
        "entry_long": "ADX < 20 AND RSI crosses above 50 from below",
        "entry_short": "ADX < 20 AND RSI crosses below 50 from above",
        "exit": "RSI crosses back OR time stop 25 OR stop 2*ATR",
        "indicators": ["ADX(14)", "RSI(14)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "cross", "swing"],
    },
)
