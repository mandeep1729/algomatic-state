"""Strategy 27: RSI Overbought Fade.

Entry Short: close < SMA200 AND RSI crosses down through 70.
Exit: RSI < 45 OR target 2.5*ATR; stop 2*ATR.
"""

from src.strats_prob.conditions import below, crosses_below
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=27,
    name="rsi_overbought_fade",
    display_name="RSI Overbought Fade",
    philosophy="Fade overbought rallies in downtrending markets for mean reversion.",
    category="mean_reversion",
    tags=["mean_reversion", "short_only", "threshold", "atr_stop", "atr_target",
          "RSI", "SMA", "ATR", "range_favor", "swing"],
    direction="short_only",
    entry_long=[],
    entry_short=[
        below("close", "sma_200"),
        crosses_below("rsi_14", 70),
    ],
    exit_long=[],
    exit_short=[
        below("rsi_14", 45),
    ],
    atr_stop_mult=2.0,
    atr_target_mult=2.5,
    required_indicators=["close", "sma_200", "rsi_14", "atr_14"],
    details={
        "entry_short": "close < SMA200 AND RSI crosses down through 70",
        "entry_long": "N/A (short only)",
        "exit": "RSI < 45 OR target 2.5*ATR; stop 2*ATR",
        "indicators": ["SMA(200)", "RSI(14)", "ATR(14)"],
        "tags": ["mean_reversion", "short_only", "threshold", "swing"],
    },
)
