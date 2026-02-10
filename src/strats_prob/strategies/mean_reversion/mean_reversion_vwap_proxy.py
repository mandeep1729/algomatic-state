"""Strategy 42: Mean Reversion to VWAP Proxy.

Proxy: typical_price_sma_20.
Entry Long: close < typical_price_sma_20 - 1.5*ATR AND RSI < 40.
Entry Short: close > typical_price_sma_20 + 1.5*ATR AND RSI > 60.
Exit: typical_price_sma_20 touch OR time 12 OR stop 2*ATR.
"""

from src.strats_prob.conditions import (
    above,
    below,
    crosses_above,
    crosses_below,
    deviation_from,
)
from src.strats_prob.strategy_def import StrategyDef

strategy = StrategyDef(
    id=42,
    name="mean_reversion_vwap_proxy",
    display_name="Mean Reversion to VWAP Proxy",
    philosophy="Large deviations from typical price SMA proxy intraday fair value; reversion is likely.",
    category="mean_reversion",
    tags=["mean_reversion", "long_short", "threshold", "time",
          "SMA", "RSI", "ATR", "range_favor", "scalp"],
    direction="long_short",
    entry_long=[
        deviation_from("close", "typical_price_sma_20", atr_mult=1.5, direction="below"),
        below("rsi_14", 40),
    ],
    entry_short=[
        deviation_from("close", "typical_price_sma_20", atr_mult=1.5, direction="above"),
        above("rsi_14", 60),
    ],
    exit_long=[
        crosses_above("close", "typical_price_sma_20"),
    ],
    exit_short=[
        crosses_below("close", "typical_price_sma_20"),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=12,
    required_indicators=["close", "typical_price_sma_20", "rsi_14", "atr_14"],
    details={
        "entry_long": "close < VWAP proxy - 1.5*ATR AND RSI < 40",
        "entry_short": "close > VWAP proxy + 1.5*ATR AND RSI > 60",
        "exit": "VWAP proxy touch OR time stop 12 OR stop 2*ATR",
        "indicators": ["Typical Price SMA(20)", "RSI(14)", "ATR(14)"],
        "tags": ["mean_reversion", "long_short", "threshold", "scalp"],
    },
)
