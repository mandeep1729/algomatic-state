"""Strategy 100: Ensemble Vote (3-strategy majority).

Signals:
  S1: EMA20 > EMA50 (bull) / < (bear)
  S2: RSI > 55 (bull) / < 45 (bear)
  S3: MACD hist > 0 (bull) / < 0 (bear)
Entry long if >= 2 bull. Short if >= 2 bear.
Exit: when vote flips OR stop 2*ATR OR target 3*ATR.
"""

import numpy as np

from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _majority_bull() -> ConditionFn:
    """True when at least 2 of 3 sub-signals are bullish."""
    def _check(df, idx):
        ema20 = float(df["ema_20"].iloc[idx])
        ema50 = float(df["ema_50"].iloc[idx])
        rsi = float(df["rsi_14"].iloc[idx])
        hist = float(df["macd_hist"].iloc[idx])
        if any(np.isnan(v) for v in [ema20, ema50, rsi, hist]):
            return False
        votes = 0
        if ema20 > ema50:
            votes += 1
        if rsi > 55:
            votes += 1
        if hist > 0:
            votes += 1
        return votes >= 2
    return _check


def _majority_bear() -> ConditionFn:
    """True when at least 2 of 3 sub-signals are bearish."""
    def _check(df, idx):
        ema20 = float(df["ema_20"].iloc[idx])
        ema50 = float(df["ema_50"].iloc[idx])
        rsi = float(df["rsi_14"].iloc[idx])
        hist = float(df["macd_hist"].iloc[idx])
        if any(np.isnan(v) for v in [ema20, ema50, rsi, hist]):
            return False
        votes = 0
        if ema20 < ema50:
            votes += 1
        if rsi < 45:
            votes += 1
        if hist < 0:
            votes += 1
        return votes >= 2
    return _check


strategy = StrategyDef(
    id=100,
    name="ensemble_vote",
    display_name="Ensemble Vote (3-Strategy Majority)",
    philosophy="Combining multiple independent signals via majority vote reduces "
               "false signals and increases conviction for entries.",
    category="regime",
    tags=["regime", "ensemble", "multi_filter", "long_short", "mixed",
          "EMA", "RSI", "MACD", "ATR", "swing"],
    direction="long_short",
    entry_long=[
        _majority_bull(),
    ],
    entry_short=[
        _majority_bear(),
    ],
    exit_long=[
        _majority_bear(),  # vote flips to bear
    ],
    exit_short=[
        _majority_bull(),  # vote flips to bull
    ],
    atr_stop_mult=2.0,
    atr_target_mult=3.0,
    required_indicators=["ema_20", "ema_50", "rsi_14", "macd_hist", "atr_14"],
    details={
        "entry_long": ">=2 of: EMA20>EMA50, RSI>55, MACD hist>0",
        "entry_short": ">=2 of: EMA20<EMA50, RSI<45, MACD hist<0",
        "exit": "Vote flips (>=2 opposite) OR stop 2*ATR OR target 3*ATR",
        "indicators": ["EMA(20)", "EMA(50)", "RSI(14)", "MACD(12,26,9)", "ATR(14)"],
        "tags": ["regime", "ensemble", "multi_filter", "long_short", "swing"],
    },
)
