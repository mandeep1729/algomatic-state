"""Strategy 79: OBV 'Break then Retest'.

Entry Long: OBV breaks obv_high_20, then price pulls back within 1*ATR of
            breakout level and closes above.
Exit: trail 2*ATR or time 40.
"""

from src.strats_prob.conditions import above, pullback_to
from src.strats_prob.strategy_def import StrategyDef


def _obv_was_above_high_20() -> "ConditionFn":
    """True when OBV was above obv_high_20 within the last 5 bars (recent breakout)."""
    import numpy as np

    def _check(df, idx):
        if idx < 5:
            return False
        for i in range(idx - 5, idx):
            obv_val = float(df["obv"].iloc[i])
            obv_high = float(df["obv_high_20"].iloc[i])
            if np.isnan(obv_val) or np.isnan(obv_high):
                continue
            if obv_val > obv_high:
                return True
        return False
    return _check


strategy = StrategyDef(
    id=79,
    name="obv_break_retest",
    display_name="OBV Break then Retest",
    philosophy="An OBV breakout followed by a price pullback and hold above support "
               "confirms volume-backed demand at the retest level.",
    category="volume_flow",
    tags=["volume_flow", "breakout", "long_only", "pullback", "atr_stop",
          "OBV", "MAX", "ATR", "vol_expand", "swing"],
    direction="long_only",
    entry_long=[
        _obv_was_above_high_20(),
        above("obv", "obv_sma_20"),
        pullback_to("ema_20", tolerance_atr_mult=1.0),
    ],
    entry_short=[],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    time_stop_bars=40,
    required_indicators=["obv", "obv_high_20", "obv_sma_20", "ema_20", "atr_14"],
    details={
        "entry_long": "OBV broke 20-bar high recently AND pullback to EMA20 within 1*ATR then close above",
        "exit": "Trailing stop 2*ATR or time stop 40 bars",
        "indicators": ["OBV", "OBV High(20)", "OBV SMA(20)", "EMA(20)", "ATR(14)"],
        "tags": ["volume_flow", "breakout", "long_only", "pullback", "swing"],
    },
)
