"""Strategy 75: Volume Spike Trend Continuation.

Entry Long: close > SMA50 AND volume > 2 * volume_sma_20 AND close in top 25% of range.
Exit: time 20 OR trail 2*ATR.
"""

from src.strats_prob.conditions import above, in_top_pct_of_range
from src.strats_prob.strategy_def import StrategyDef


def _volume_spike() -> "ConditionFn":
    """True when volume exceeds 2x its 20-period SMA."""
    import numpy as np

    def _check(df, idx):
        vol = float(df["volume"].iloc[idx])
        vol_sma = float(df["volume_sma_20"].iloc[idx])
        if np.isnan(vol) or np.isnan(vol_sma) or vol_sma == 0:
            return False
        return vol > 2.0 * vol_sma
    return _check


strategy = StrategyDef(
    id=75,
    name="volume_spike_trend",
    display_name="Volume Spike Trend Continuation",
    philosophy="Unusually high volume in an uptrend with a strong close signals "
               "institutional participation and trend continuation.",
    category="volume_flow",
    tags=["volume_flow", "trend", "long_only", "threshold", "time",
          "SMA", "ATR", "trend_favor", "swing"],
    direction="long_only",
    entry_long=[
        above("close", "sma_50"),
        _volume_spike(),
        in_top_pct_of_range(0.25),
    ],
    entry_short=[],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    time_stop_bars=20,
    required_indicators=["sma_50", "volume", "volume_sma_20", "atr_14"],
    details={
        "entry_long": "Close > SMA50 AND volume > 2*volume_sma_20 AND close in top 25% of range",
        "exit": "Time stop 20 bars OR trailing stop 2*ATR",
        "indicators": ["SMA(50)", "Volume SMA(20)", "ATR(14)"],
        "tags": ["volume_flow", "trend", "long_only", "swing"],
    },
)
