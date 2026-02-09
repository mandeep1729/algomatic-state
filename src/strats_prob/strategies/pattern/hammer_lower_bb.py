"""Strategy 83: Hammer at Lower BB.

Entry Long: cdl_hammer > 0 AND low < BB lower.
Exit: BB middle OR time 20 OR stop 2*ATR.
"""

from src.strats_prob.conditions import above, candle_bullish, below
from src.strats_prob.strategy_def import StrategyDef


def _low_below_bb_lower() -> "ConditionFn":
    """True when bar low is below the lower Bollinger Band."""
    import numpy as np

    def _check(df, idx):
        low_val = float(df["low"].iloc[idx])
        bb_low = float(df["bb_lower"].iloc[idx])
        if np.isnan(low_val) or np.isnan(bb_low):
            return False
        return low_val < bb_low
    return _check


strategy = StrategyDef(
    id=83,
    name="hammer_lower_bb",
    display_name="Hammer at Lower BB",
    philosophy="A hammer candle at the lower Bollinger Band signals rejection of "
               "lower prices and potential mean reversion.",
    category="pattern",
    tags=["pattern", "mean_reversion", "long_only", "pattern", "time",
          "CDLHAMMER", "BBANDS", "ATR", "range_favor", "swing"],
    direction="long_only",
    entry_long=[
        candle_bullish("cdl_hammer"),
        _low_below_bb_lower(),
    ],
    entry_short=[],
    exit_long=[
        above("close", "bb_middle"),
    ],
    exit_short=[],
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["cdl_hammer", "bb_lower", "bb_middle", "atr_14"],
    details={
        "entry_long": "Hammer candle AND low < BB lower",
        "exit": "BB middle touch OR time stop 20 bars OR stop 2*ATR",
        "indicators": ["CDL_HAMMER", "BBANDS(20,2,2)", "ATR(14)"],
        "tags": ["pattern", "mean_reversion", "long_only", "swing"],
    },
)
