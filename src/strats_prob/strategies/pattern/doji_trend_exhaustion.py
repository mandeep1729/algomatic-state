"""Strategy 87: Doji + Trend Exhaustion (ATR spike).

Entry Long: cdl_doji != 0 AND range > 1.8*ATR AND RSI < 45.
Entry Short: cdl_doji != 0 AND range > 1.8*ATR AND RSI > 55.
Exit: time 20 OR target 2.5*ATR OR stop 2*ATR.
"""

from src.strats_prob.conditions import below, above, range_exceeds_atr
from src.strats_prob.strategy_def import StrategyDef


def _doji_present() -> "ConditionFn":
    """True when a doji candle pattern is detected (non-zero value)."""
    import numpy as np

    def _check(df, idx):
        v = float(df["cdl_doji"].iloc[idx])
        return not np.isnan(v) and v != 0
    return _check


strategy = StrategyDef(
    id=87,
    name="doji_trend_exhaustion",
    display_name="Doji + Trend Exhaustion",
    philosophy="A doji on a wide-range bar with extreme RSI signals indecision "
               "after exhaustion, often preceding a reversal.",
    category="pattern",
    tags=["pattern", "mean_reversion", "volatility", "long_short", "pattern",
          "time", "CDLDOJI", "ATR", "RSI", "range_favor", "swing"],
    direction="long_short",
    entry_long=[
        _doji_present(),
        range_exceeds_atr(1.8),
        below("rsi_14", 45),
    ],
    entry_short=[
        _doji_present(),
        range_exceeds_atr(1.8),
        above("rsi_14", 55),
    ],
    exit_long=[],
    exit_short=[],
    atr_stop_mult=2.0,
    atr_target_mult=2.5,
    time_stop_bars=20,
    required_indicators=["cdl_doji", "atr_14", "rsi_14"],
    details={
        "entry_long": "Doji candle AND bar range > 1.8*ATR AND RSI < 45",
        "entry_short": "Doji candle AND bar range > 1.8*ATR AND RSI > 55",
        "exit": "Time stop 20 bars OR target 2.5*ATR OR stop 2*ATR",
        "indicators": ["CDL_DOJI", "ATR(14)", "RSI(14)"],
        "tags": ["pattern", "mean_reversion", "volatility", "long_short", "swing"],
    },
)
