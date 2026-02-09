"""Strategy 26: RSI Oversold Bounce.

Entry Long: close > SMA200 AND RSI crosses up through 30.
Exit: target at RSI > 55 OR 2.5*ATR target; stop 2*ATR; time stop 20.
"""

from src.strats_prob.conditions import above, crosses_above
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=26,
    name="rsi_oversold_bounce",
    display_name="RSI Oversold Bounce",
    philosophy="Buy oversold dips in uptrending markets for mean reversion to the norm.",
    category="mean_reversion",
    tags=["mean_reversion", "long_only", "threshold", "atr_stop", "atr_target",
          "RSI", "SMA", "ATR", "range_favor", "swing"],
    direction="long_only",
    entry_long=[
        above("close", "sma_200"),
        crosses_above("rsi_14", 30),
    ],
    entry_short=[],
    exit_long=[
        above("rsi_14", 55),
    ],
    exit_short=[],
    atr_stop_mult=2.0,
    atr_target_mult=2.5,
    time_stop_bars=20,
    required_indicators=["close", "sma_200", "rsi_14", "atr_14"],
    details={
        "entry_long": "close > SMA200 AND RSI crosses up through 30",
        "entry_short": "N/A (long only)",
        "exit": "RSI > 55 OR target 2.5*ATR; stop 2*ATR; time stop 20 bars",
        "indicators": ["SMA(200)", "RSI(14)", "ATR(14)"],
        "tags": ["mean_reversion", "long_only", "threshold", "swing"],
    },
)
