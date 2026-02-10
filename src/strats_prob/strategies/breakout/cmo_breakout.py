"""Strategy 70: CMO Breakout.

Entry Long: CMO(14) > +40 AND close breaks donchian_high_10.
Entry Short: CMO < -40 AND close breaks donchian_low_10.
Exit: CMO back within +/-10 OR stop 2*ATR.
"""

import numpy as np
import pandas as pd

from src.strats_prob.conditions import (
    above,
    below,
    breaks_above_level,
    breaks_below_level,
)
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _cmo_within_10(df: pd.DataFrame, idx: int) -> bool:
    """True when CMO is between -10 and +10 (neutral zone)."""
    cmo = float(df["cmo_14"].iloc[idx])
    if np.isnan(cmo) or np.isinf(cmo):
        return False
    return -10 <= cmo <= 10


strategy = StrategyDef(
    id=70,
    name="cmo_breakout",
    display_name="CMO Breakout",
    philosophy="Chande Momentum Oscillator extremes confirm price breakout direction.",
    category="breakout",
    tags=["breakout", "long_short", "threshold", "time",
          "CMO", "MAX", "MIN", "ATR", "vol_expand", "swing"],
    direction="long_short",
    entry_long=[
        above("cmo_14", 40),
        breaks_above_level("donchian_high_10"),
    ],
    entry_short=[
        below("cmo_14", -40),
        breaks_below_level("donchian_low_10"),
    ],
    exit_long=[
        _cmo_within_10,
    ],
    exit_short=[
        _cmo_within_10,
    ],
    atr_stop_mult=2.0,
    required_indicators=["cmo_14", "donchian_high_10", "donchian_low_10", "atr_14"],
    details={
        "entry_long": "CMO(14) > +40 AND close breaks 10-bar Donchian high",
        "entry_short": "CMO(14) < -40 AND close breaks 10-bar Donchian low",
        "exit": "CMO back within +/-10 OR stop 2*ATR",
        "indicators": ["CMO(14)", "Donchian(10)", "ATR(14)"],
        "tags": ["breakout", "long_short", "swing"],
    },
)
