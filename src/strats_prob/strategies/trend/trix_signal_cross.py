"""Strategy 8: TRIX Signal Cross.

Entry: TRIX(15) crosses above/below its SMA(9).
Exit: opposite cross OR stop 2*ATR.

Note: We compute the TRIX SMA(9) inline since there is no pre-computed column.
"""

import numpy as np
import pandas as pd

from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _trix_sma(df: pd.DataFrame, idx: int, period: int = 9) -> float:
    """Compute SMA of trix_15 at bar idx over `period` bars."""
    if idx < period - 1:
        return float("nan")
    vals = df["trix_15"].iloc[idx - period + 1: idx + 1]
    if vals.isna().any():
        return float("nan")
    return float(vals.mean())


def _trix_crosses_above_sma(df: pd.DataFrame, idx: int) -> bool:
    """True when trix_15 crosses above its 9-period SMA."""
    if idx < 10:
        return False
    curr_trix = float(df["trix_15"].iloc[idx])
    prev_trix = float(df["trix_15"].iloc[idx - 1])
    curr_sma = _trix_sma(df, idx)
    prev_sma = _trix_sma(df, idx - 1)
    if any(np.isnan(v) or np.isinf(v) for v in [curr_trix, prev_trix, curr_sma, prev_sma]):
        return False
    return prev_trix <= prev_sma and curr_trix > curr_sma


def _trix_crosses_below_sma(df: pd.DataFrame, idx: int) -> bool:
    """True when trix_15 crosses below its 9-period SMA."""
    if idx < 10:
        return False
    curr_trix = float(df["trix_15"].iloc[idx])
    prev_trix = float(df["trix_15"].iloc[idx - 1])
    curr_sma = _trix_sma(df, idx)
    prev_sma = _trix_sma(df, idx - 1)
    if any(np.isnan(v) or np.isinf(v) for v in [curr_trix, prev_trix, curr_sma, prev_sma]):
        return False
    return prev_trix >= prev_sma and curr_trix < curr_sma


strategy = StrategyDef(
    id=8,
    name="trix_signal_cross",
    display_name="TRIX Signal Cross",
    philosophy="Triple-smoothed EMA rate of change filters noise; signal cross confirms trend.",
    category="trend",
    tags=["trend", "long_short", "cross", "signal", "atr_stop", "TRIX", "ATR",
          "trend_favor", "swing"],
    direction="long_short",
    entry_long=[
        _trix_crosses_above_sma,
    ],
    entry_short=[
        _trix_crosses_below_sma,
    ],
    exit_long=[
        _trix_crosses_below_sma,
    ],
    exit_short=[
        _trix_crosses_above_sma,
    ],
    atr_stop_mult=2.0,
    required_indicators=["trix_15", "atr_14"],
    details={
        "entry_long": "TRIX(15) crosses above its SMA(9)",
        "entry_short": "TRIX(15) crosses below its SMA(9)",
        "exit": "Opposite cross OR stop 2*ATR",
        "indicators": ["TRIX(15)", "SMA(9) of TRIX", "ATR(14)"],
        "tags": ["trend", "long_short", "cross", "swing"],
    },
)
