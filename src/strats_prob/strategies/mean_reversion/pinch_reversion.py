"""Strategy 50: 'Pinch' Reversion (ATR contraction then snap).

Setup: ATR(14) below its SMA(50) by 20% AND ADX < 20.
Entry Long: RSI crosses above 50 after being < 40.
Entry Short: RSI crosses below 50 after being > 60.
Exit: time 25 OR stop 2*ATR OR RSI crosses back.
"""

import numpy as np
import pandas as pd

from src.strats_prob.conditions import (
    below,
    crosses_above,
    crosses_below,
    was_below_then_crosses_above,
    was_above_then_crosses_below,
)
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _atr_contracted(pct: float = 0.20) -> ConditionFn:
    """True when ATR(14) is below its SMA(50) by at least `pct` fraction."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        atr_val = float(df["atr_14"].iloc[idx])
        atr_sma = float(df["atr_sma_50"].iloc[idx])
        if any(np.isnan(v) or np.isinf(v) for v in [atr_val, atr_sma]):
            return False
        if atr_sma == 0:
            return False
        return atr_val < atr_sma * (1.0 - pct)
    return _check


strategy = StrategyDef(
    id=50,
    name="pinch_reversion",
    display_name="Pinch Reversion (ATR Contraction Snap)",
    philosophy="Volatility contraction (ATR pinch) with low ADX sets up a coiled spring; RSI confirms direction.",
    category="mean_reversion",
    tags=["mean_reversion", "volatility", "long_short", "threshold", "time",
          "ATR", "ADX", "RSI", "vol_contract", "swing"],
    direction="long_short",
    entry_long=[
        _atr_contracted(0.20),
        below("adx_14", 20),
        was_below_then_crosses_above("rsi_14", 50, lookback=10),
    ],
    entry_short=[
        _atr_contracted(0.20),
        below("adx_14", 20),
        was_above_then_crosses_below("rsi_14", 50, lookback=10),
    ],
    exit_long=[
        crosses_below("rsi_14", 50),
    ],
    exit_short=[
        crosses_above("rsi_14", 50),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=25,
    required_indicators=["atr_14", "atr_sma_50", "adx_14", "rsi_14"],
    details={
        "entry_long": "ATR below SMA(ATR,50) by 20% AND ADX < 20 AND RSI crosses above 50 after being < 40",
        "entry_short": "ATR below SMA(ATR,50) by 20% AND ADX < 20 AND RSI crosses below 50 after being > 60",
        "exit": "RSI crosses back OR time stop 25 OR stop 2*ATR",
        "indicators": ["ATR(14)", "SMA(ATR,50)", "ADX(14)", "RSI(14)"],
        "tags": ["mean_reversion", "volatility", "long_short", "swing"],
    },
)
