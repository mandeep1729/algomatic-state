"""Strategy 61: RSI Breakout (momentum ignition).

Entry Long: RSI crosses above 60 AND close breaks donchian_high_10.
Entry Short: RSI crosses below 40 AND close breaks donchian_low_10.
Exit: RSI returns to 50 OR time 25 OR stop 2*ATR.
"""

from src.strats_prob.conditions import (
    breaks_above_level,
    breaks_below_level,
    crosses_above,
    crosses_below,
)
from src.strats_prob.strategy_def import StrategyDef


def _rsi_returns_to_50_from_above(df, idx):
    """True when RSI crosses back down through 50 (for long exit)."""
    if idx < 1:
        return False
    curr = float(df["rsi_14"].iloc[idx])
    prev = float(df["rsi_14"].iloc[idx - 1])
    import numpy as np
    if np.isnan(curr) or np.isnan(prev):
        return False
    return prev >= 50 and curr < 50


def _rsi_returns_to_50_from_below(df, idx):
    """True when RSI crosses back up through 50 (for short exit)."""
    if idx < 1:
        return False
    curr = float(df["rsi_14"].iloc[idx])
    prev = float(df["rsi_14"].iloc[idx - 1])
    import numpy as np
    if np.isnan(curr) or np.isnan(prev):
        return False
    return prev <= 50 and curr > 50


strategy = StrategyDef(
    id=61,
    name="rsi_breakout",
    display_name="RSI Breakout (Momentum Ignition)",
    philosophy="RSI crossing momentum threshold confirms price breakout as genuine.",
    category="breakout",
    tags=["breakout", "long_short", "threshold", "time", "atr_stop",
          "RSI", "MAX", "MIN", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        crosses_above("rsi_14", 60),
        breaks_above_level("donchian_high_10"),
    ],
    entry_short=[
        crosses_below("rsi_14", 40),
        breaks_below_level("donchian_low_10"),
    ],
    exit_long=[
        _rsi_returns_to_50_from_above,
    ],
    exit_short=[
        _rsi_returns_to_50_from_below,
    ],
    atr_stop_mult=2.0,
    time_stop_bars=25,
    required_indicators=["rsi_14", "donchian_high_10", "donchian_low_10", "atr_14"],
    details={
        "entry_long": "RSI crosses above 60 AND close breaks 10-bar high",
        "entry_short": "RSI crosses below 40 AND close breaks 10-bar low",
        "exit": "RSI returns to 50 OR time 25 bars OR stop 2*ATR",
        "indicators": ["RSI(14)", "Donchian(10)", "ATR(14)"],
        "tags": ["breakout", "long_short", "swing"],
    },
)
