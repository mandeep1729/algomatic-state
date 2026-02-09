"""Strategy 19: EMA Ribbon Compression -> Break.

Setup: |EMA20-EMA50| < 0.5*ATR for 10 bars.
Entry Long: close breaks above max(EMA20,EMA50) + 0.5*ATR.
Entry Short: close breaks below min(EMA20,EMA50) - 0.5*ATR.
Exit: opposite break OR trail 2*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _ribbon_compressed(df: pd.DataFrame, idx: int, lookback: int = 10) -> bool:
    """True when |EMA20-EMA50| < 0.5*ATR for the last `lookback` bars."""
    if idx < lookback - 1:
        return False
    for i in range(idx - lookback + 1, idx + 1):
        ema20 = float(df["ema_20"].iloc[i])
        ema50 = float(df["ema_50"].iloc[i])
        atr = float(df["atr_14"].iloc[i])
        if any(np.isnan(v) or np.isinf(v) for v in [ema20, ema50, atr]):
            return False
        if abs(ema20 - ema50) >= 0.5 * atr:
            return False
    return True


def _entry_long_ribbon_break(df: pd.DataFrame, idx: int) -> bool:
    """True when ribbon is compressed AND close breaks above max(EMA20,EMA50) + 0.5*ATR."""
    if not _ribbon_compressed(df, idx):
        return False
    close = float(df["close"].iloc[idx])
    ema20 = float(df["ema_20"].iloc[idx])
    ema50 = float(df["ema_50"].iloc[idx])
    atr = float(df["atr_14"].iloc[idx])
    if any(np.isnan(v) or np.isinf(v) for v in [close, ema20, ema50, atr]):
        return False
    upper = max(ema20, ema50) + 0.5 * atr
    return close > upper


def _entry_short_ribbon_break(df: pd.DataFrame, idx: int) -> bool:
    """True when ribbon is compressed AND close breaks below min(EMA20,EMA50) - 0.5*ATR."""
    if not _ribbon_compressed(df, idx):
        return False
    close = float(df["close"].iloc[idx])
    ema20 = float(df["ema_20"].iloc[idx])
    ema50 = float(df["ema_50"].iloc[idx])
    atr = float(df["atr_14"].iloc[idx])
    if any(np.isnan(v) or np.isinf(v) for v in [close, ema20, ema50, atr]):
        return False
    lower = min(ema20, ema50) - 0.5 * atr
    return close < lower


def _exit_long_ribbon(df: pd.DataFrame, idx: int) -> bool:
    """True when close falls below min(EMA20, EMA50) - 0.5*ATR."""
    close = float(df["close"].iloc[idx])
    ema20 = float(df["ema_20"].iloc[idx])
    ema50 = float(df["ema_50"].iloc[idx])
    atr = float(df["atr_14"].iloc[idx])
    if any(np.isnan(v) or np.isinf(v) for v in [close, ema20, ema50, atr]):
        return False
    lower = min(ema20, ema50) - 0.5 * atr
    return close < lower


def _exit_short_ribbon(df: pd.DataFrame, idx: int) -> bool:
    """True when close rises above max(EMA20, EMA50) + 0.5*ATR."""
    close = float(df["close"].iloc[idx])
    ema20 = float(df["ema_20"].iloc[idx])
    ema50 = float(df["ema_50"].iloc[idx])
    atr = float(df["atr_14"].iloc[idx])
    if any(np.isnan(v) or np.isinf(v) for v in [close, ema20, ema50, atr]):
        return False
    upper = max(ema20, ema50) + 0.5 * atr
    return close > upper


strategy = StrategyDef(
    id=19,
    name="ema_ribbon_compression_break",
    display_name="EMA Ribbon Compression Break",
    philosophy="Tight EMA compression signals coiling energy; breakout indicates directional resolve.",
    category="trend",
    tags=["trend", "breakout", "long_short", "breakout", "atr_stop", "EMA", "ATR",
          "vol_contract_expand", "swing"],
    direction="long_short",
    entry_long=[
        _entry_long_ribbon_break,
    ],
    entry_short=[
        _entry_short_ribbon_break,
    ],
    exit_long=[
        _exit_long_ribbon,
    ],
    exit_short=[
        _exit_short_ribbon,
    ],
    atr_stop_mult=2.0,
    trailing_atr_mult=2.0,
    required_indicators=["ema_20", "ema_50", "atr_14"],
    details={
        "entry_long": "|EMA20-EMA50| < 0.5*ATR for 10 bars THEN close > max(EMA20,EMA50)+0.5*ATR",
        "entry_short": "|EMA20-EMA50| < 0.5*ATR for 10 bars THEN close < min(EMA20,EMA50)-0.5*ATR",
        "exit": "Opposite break OR trail 2*ATR",
        "indicators": ["EMA(20)", "EMA(50)", "ATR(14)"],
        "tags": ["trend", "breakout", "long_short", "swing"],
    },
)
