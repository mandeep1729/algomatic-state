"""Strategy 92: Volatility Regime Switch (ATR vs ATR-SMA).

Regime Expand: ATR > atr_sma_50 -> breakout (close > donchian_high_20).
Regime Contract: ATR < 0.85 * atr_sma_50 -> mean reversion (close < typical_price_sma_20 - 1.5*ATR).
Exit: trail 2*ATR.
"""

import numpy as np

from src.strats_prob.conditions import (
    above,
    below,
    breaks_above_level,
    breaks_below_level,
    all_of,
    any_of,
)
from src.strats_prob.strategy_def import ConditionFn, StrategyDef


def _atr_below_contracted_sma() -> ConditionFn:
    """True when ATR < 0.85 * atr_sma_50 (volatility contraction)."""
    def _check(df, idx):
        atr = float(df["atr_14"].iloc[idx])
        atr_sma = float(df["atr_sma_50"].iloc[idx])
        if np.isnan(atr) or np.isnan(atr_sma):
            return False
        return atr < 0.85 * atr_sma
    return _check


def _mean_rev_long() -> ConditionFn:
    """Mean reversion long: close deviates below typical_price_sma_20 by > 1.5*ATR."""
    def _check(df, idx):
        close_val = float(df["close"].iloc[idx])
        tp_sma = float(df["typical_price_sma_20"].iloc[idx])
        atr = float(df["atr_14"].iloc[idx])
        if np.isnan(close_val) or np.isnan(tp_sma) or np.isnan(atr):
            return False
        return (tp_sma - close_val) > 1.5 * atr
    return _check


def _mean_rev_short() -> ConditionFn:
    """Mean reversion short: close deviates above typical_price_sma_20 by > 1.5*ATR."""
    def _check(df, idx):
        close_val = float(df["close"].iloc[idx])
        tp_sma = float(df["typical_price_sma_20"].iloc[idx])
        atr = float(df["atr_14"].iloc[idx])
        if np.isnan(close_val) or np.isnan(tp_sma) or np.isnan(atr):
            return False
        return (close_val - tp_sma) > 1.5 * atr
    return _check


# Expansion regime: breakout entries
_expand_long = all_of(
    above("atr_14", "atr_sma_50"),
    breaks_above_level("donchian_high_20"),
)

_expand_short = all_of(
    above("atr_14", "atr_sma_50"),
    breaks_below_level("donchian_low_20"),
)

# Contraction regime: mean reversion entries
_contract_long = all_of(
    _atr_below_contracted_sma(),
    _mean_rev_long(),
)

_contract_short = all_of(
    _atr_below_contracted_sma(),
    _mean_rev_short(),
)

strategy = StrategyDef(
    id=92,
    name="volatility_regime_switch",
    display_name="Volatility Regime Switch",
    philosophy="Switching between breakout and mean reversion based on volatility regime "
               "aligns strategy behavior with current market conditions.",
    category="regime",
    tags=["regime", "volatility", "long_short", "threshold", "mixed",
          "ATR", "BBANDS", "MAX", "MIN", "swing"],
    direction="long_short",
    entry_long=[
        any_of(_expand_long, _contract_long),
    ],
    entry_short=[
        any_of(_expand_short, _contract_short),
    ],
    exit_long=[],
    exit_short=[],
    trailing_atr_mult=2.0,
    atr_stop_mult=2.0,
    required_indicators=["atr_14", "atr_sma_50", "donchian_high_20",
                         "donchian_low_20", "typical_price_sma_20"],
    details={
        "entry_long": "Expand: ATR>ATR_SMA50 AND break Donchian high; Contract: ATR<0.85*ATR_SMA50 AND oversold",
        "entry_short": "Expand: ATR>ATR_SMA50 AND break Donchian low; Contract: ATR<0.85*ATR_SMA50 AND overbought",
        "exit": "Trailing stop 2*ATR",
        "indicators": ["ATR(14)", "ATR SMA(50)", "Donchian(20)", "Typical Price SMA(20)"],
        "tags": ["regime", "volatility", "long_short", "swing"],
    },
)
