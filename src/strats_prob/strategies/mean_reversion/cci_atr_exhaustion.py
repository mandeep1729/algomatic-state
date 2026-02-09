"""Strategy 45: CCI + ATR Exhaustion Fade.

Entry Long: CCI < -200 AND (high - low) > 2*ATR, then next close higher.
Entry Short: CCI > +200 AND range > 2*ATR, then next close lower.
Exit: CCI back above -100 / below +100 OR target 3*ATR; stop 2.5*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _cci_exhaustion_long() -> ConditionFn:
    """True when CCI was < -200 with wide range on prior bar AND current close is higher."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < 1:
            return False
        # Prior bar conditions
        cci_prev = float(df["cci_20"].iloc[idx - 1])
        high_prev = float(df["high"].iloc[idx - 1])
        low_prev = float(df["low"].iloc[idx - 1])
        atr_prev = float(df["atr_14"].iloc[idx - 1])
        close_prev = float(df["close"].iloc[idx - 1])
        close_now = float(df["close"].iloc[idx])
        if any(np.isnan(v) or np.isinf(v) for v in [cci_prev, high_prev, low_prev, atr_prev, close_prev, close_now]):
            return False
        bar_range = high_prev - low_prev
        return cci_prev < -200 and bar_range > 2 * atr_prev and close_now > close_prev
    return _check


def _cci_exhaustion_short() -> ConditionFn:
    """True when CCI was > +200 with wide range on prior bar AND current close is lower."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < 1:
            return False
        cci_prev = float(df["cci_20"].iloc[idx - 1])
        high_prev = float(df["high"].iloc[idx - 1])
        low_prev = float(df["low"].iloc[idx - 1])
        atr_prev = float(df["atr_14"].iloc[idx - 1])
        close_prev = float(df["close"].iloc[idx - 1])
        close_now = float(df["close"].iloc[idx])
        if any(np.isnan(v) or np.isinf(v) for v in [cci_prev, high_prev, low_prev, atr_prev, close_prev, close_now]):
            return False
        bar_range = high_prev - low_prev
        return cci_prev > 200 and bar_range > 2 * atr_prev and close_now < close_prev
    return _check


strategy = StrategyDef(
    id=45,
    name="cci_atr_exhaustion",
    display_name="CCI + ATR Exhaustion Fade",
    philosophy="Extreme CCI with volatile range signals panic; fading the exhaustion captures the rebound.",
    category="mean_reversion",
    tags=["mean_reversion", "volatility", "long_short", "threshold", "atr_stop",
          "atr_target", "CCI", "ATR", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        _cci_exhaustion_long(),
    ],
    entry_short=[
        _cci_exhaustion_short(),
    ],
    exit_long=[
        above("cci_20", -100),
    ],
    exit_short=[
        below("cci_20", 100),
    ],
    atr_stop_mult=2.5,
    atr_target_mult=3.0,
    required_indicators=["close", "high", "low", "cci_20", "atr_14"],
    details={
        "entry_long": "CCI < -200 AND bar range > 2*ATR, then next close higher",
        "entry_short": "CCI > +200 AND bar range > 2*ATR, then next close lower",
        "exit": "CCI back above -100 / below +100 OR target 3*ATR; stop 2.5*ATR",
        "indicators": ["CCI(20)", "ATR(14)"],
        "tags": ["mean_reversion", "volatility", "long_short", "swing"],
    },
)
