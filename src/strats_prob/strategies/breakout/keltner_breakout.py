"""Strategy 59: Keltner-style Breakout (ATR around EMA).

Bands: EMA20 +/- 1.5*ATR (computed inline).
Entry: close breaks band.
Exit: return to EMA20 OR target 3*ATR OR stop 2*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.conditions import crosses_above, crosses_below
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _close_above_keltner_upper(df: pd.DataFrame, idx: int) -> bool:
    """True when close breaks above EMA20 + 1.5*ATR."""
    if idx < 1:
        return False
    close_now = float(df["close"].iloc[idx])
    close_prev = float(df["close"].iloc[idx - 1])
    ema_now = float(df["ema_20"].iloc[idx])
    ema_prev = float(df["ema_20"].iloc[idx - 1])
    atr_now = float(df["atr_14"].iloc[idx])
    atr_prev = float(df["atr_14"].iloc[idx - 1])
    if any(np.isnan(v) or np.isinf(v) for v in [close_now, close_prev, ema_now, ema_prev, atr_now, atr_prev]):
        return False
    upper_now = ema_now + 1.5 * atr_now
    upper_prev = ema_prev + 1.5 * atr_prev
    return close_prev <= upper_prev and close_now > upper_now


def _close_below_keltner_lower(df: pd.DataFrame, idx: int) -> bool:
    """True when close breaks below EMA20 - 1.5*ATR."""
    if idx < 1:
        return False
    close_now = float(df["close"].iloc[idx])
    close_prev = float(df["close"].iloc[idx - 1])
    ema_now = float(df["ema_20"].iloc[idx])
    ema_prev = float(df["ema_20"].iloc[idx - 1])
    atr_now = float(df["atr_14"].iloc[idx])
    atr_prev = float(df["atr_14"].iloc[idx - 1])
    if any(np.isnan(v) or np.isinf(v) for v in [close_now, close_prev, ema_now, ema_prev, atr_now, atr_prev]):
        return False
    lower_now = ema_now - 1.5 * atr_now
    lower_prev = ema_prev - 1.5 * atr_prev
    return close_prev >= lower_prev and close_now < lower_now


strategy = StrategyDef(
    id=59,
    name="keltner_breakout",
    display_name="Keltner-style Breakout",
    philosophy="Keltner channel breakout signals strong moves beyond normal volatility range.",
    category="breakout",
    tags=["breakout", "long_short", "breakout", "atr_stop", "atr_target",
          "EMA", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        _close_above_keltner_upper,
    ],
    entry_short=[
        _close_below_keltner_lower,
    ],
    exit_long=[
        crosses_below("close", "ema_20"),
    ],
    exit_short=[
        crosses_above("close", "ema_20"),
    ],
    atr_stop_mult=2.0,
    atr_target_mult=3.0,
    required_indicators=["ema_20", "atr_14"],
    details={
        "entry_long": "Close breaks above EMA20 + 1.5*ATR",
        "entry_short": "Close breaks below EMA20 - 1.5*ATR",
        "exit": "Return to EMA20 OR target 3*ATR OR stop 2*ATR",
        "indicators": ["EMA(20)", "ATR(14)"],
        "tags": ["breakout", "long_short", "swing"],
    },
)
