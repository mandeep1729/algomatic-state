"""Strategy 84: Shooting Star at Upper BB.

Entry Short: cdl_shooting_star < 0 AND high > BB upper.
Exit: BB middle OR time 20 OR stop 2*ATR.
"""

from src.strats_prob.conditions import below, candle_bearish
from src.strats_prob.strategy_def import StrategyDef


def _high_above_bb_upper() -> "ConditionFn":
    """True when bar high is above the upper Bollinger Band."""
    import numpy as np

    def _check(df, idx):
        high_val = float(df["high"].iloc[idx])
        bb_up = float(df["bb_upper"].iloc[idx])
        if np.isnan(high_val) or np.isnan(bb_up):
            return False
        return high_val > bb_up
    return _check


strategy = StrategyDef(
    id=84,
    name="shooting_star_upper_bb",
    display_name="Shooting Star at Upper BB",
    philosophy="A shooting star at the upper Bollinger Band signals rejection of "
               "higher prices and potential mean reversion downward.",
    category="pattern",
    tags=["pattern", "mean_reversion", "short_only", "pattern", "time",
          "CDLSHOOTINGSTAR", "BBANDS", "ATR", "range_favor", "swing"],
    direction="short_only",
    entry_long=[],
    entry_short=[
        candle_bearish("cdl_shooting_star"),
        _high_above_bb_upper(),
    ],
    exit_long=[],
    exit_short=[
        below("close", "bb_middle"),
    ],
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["cdl_shooting_star", "bb_upper", "bb_middle", "atr_14"],
    details={
        "entry_short": "Shooting star candle AND high > BB upper",
        "exit": "BB middle touch OR time stop 20 bars OR stop 2*ATR",
        "indicators": ["CDL_SHOOTING_STAR", "BBANDS(20,2,2)", "ATR(14)"],
        "tags": ["pattern", "mean_reversion", "short_only", "swing"],
    },
)
