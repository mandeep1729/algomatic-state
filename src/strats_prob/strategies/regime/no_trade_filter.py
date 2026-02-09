"""Strategy 94: 'No-Trade' Filter Strategy.

Rule: ADX between 18 and 35 AND ATR not in bottom 20% of last 200 bars.
Then: ROC crosses above 0 AND close > SMA200 (long).
Exit: time 15 OR stop 2*ATR.
"""

import numpy as np

from src.strats_prob.conditions import above, below, crosses_above, crosses_below
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _adx_in_tradeable_range() -> ConditionFn:
    """True when ADX is between 18 and 35 (tradeable range)."""
    def _check(df, idx):
        adx = float(df["adx_14"].iloc[idx])
        if np.isnan(adx):
            return False
        return 18 <= adx <= 35
    return _check


def _atr_not_bottom_20pct(lookback: int = 200) -> ConditionFn:
    """True when ATR is not in the bottom 20% of its range over lookback bars."""
    def _check(df, idx):
        if idx < lookback:
            return False
        atr_now = float(df["atr_14"].iloc[idx])
        if np.isnan(atr_now):
            return False
        window = df["atr_14"].iloc[max(0, idx - lookback + 1): idx + 1].dropna()
        if len(window) < 20:
            return False
        threshold = float(np.percentile(window, 20))
        return atr_now > threshold
    return _check


strategy = StrategyDef(
    id=94,
    name="no_trade_filter",
    display_name="No-Trade Filter Strategy",
    philosophy="Filtering out unfavorable conditions (too weak or too strong trend, "
               "too low volatility) before entering improves overall strategy quality.",
    category="regime",
    tags=["regime", "long_short", "threshold", "time",
          "ATR", "ADX", "risk:tight", "scalp"],
    direction="long_short",
    entry_long=[
        _adx_in_tradeable_range(),
        _atr_not_bottom_20pct(200),
        crosses_above("roc_10", 0),
        above("close", "sma_200"),
    ],
    entry_short=[
        _adx_in_tradeable_range(),
        _atr_not_bottom_20pct(200),
        crosses_below("roc_10", 0),
        below("close", "sma_200"),
    ],
    exit_long=[],
    exit_short=[],
    atr_stop_mult=2.0,
    time_stop_bars=15,
    required_indicators=["adx_14", "atr_14", "roc_10", "sma_200"],
    details={
        "entry_long": "ADX 18-35 AND ATR not bottom 20% AND ROC crosses above 0 AND close > SMA200",
        "entry_short": "ADX 18-35 AND ATR not bottom 20% AND ROC crosses below 0 AND close < SMA200",
        "exit": "Time stop 15 bars OR stop 2*ATR",
        "indicators": ["ADX(14)", "ATR(14)", "ROC(10)", "SMA(200)"],
        "tags": ["regime", "long_short", "threshold", "scalp"],
    },
)
