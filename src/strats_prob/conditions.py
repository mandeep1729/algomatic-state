"""Reusable condition factory functions for strategy definitions.

Each factory returns a ConditionFn: Callable[[pd.DataFrame, int], bool]
that receives the full features DataFrame and the current bar index (iloc position).
"""

import logging
from typing import Union

import numpy as np
import pandas as pd

from src.strats_prob.strategy_def import ConditionFn

logger = logging.getLogger(__name__)

Ref = Union[str, float, int]


def _val(df: pd.DataFrame, idx: int, ref: Ref) -> float:
    """Resolve a reference to a numeric value at the given bar index."""
    if isinstance(ref, str):
        return float(df[ref].iloc[idx])
    return float(ref)


def _safe(val: float) -> bool:
    """Return False if val is NaN or Inf."""
    return not (np.isnan(val) or np.isinf(val))


# ---------------------------------------------------------------------------
# Cross conditions
# ---------------------------------------------------------------------------


def crosses_above(col_a: str, col_b_or_value: Ref) -> ConditionFn:
    """True when col_a crosses above col_b (or a fixed value) at bar idx."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < 1:
            return False
        curr_a = float(df[col_a].iloc[idx])
        prev_a = float(df[col_a].iloc[idx - 1])
        curr_b = _val(df, idx, col_b_or_value)
        prev_b = _val(df, idx - 1, col_b_or_value)
        if not all(_safe(v) for v in [curr_a, prev_a, curr_b, prev_b]):
            return False
        return prev_a <= prev_b and curr_a > curr_b
    return _check


def crosses_below(col_a: str, col_b_or_value: Ref) -> ConditionFn:
    """True when col_a crosses below col_b (or a fixed value) at bar idx."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < 1:
            return False
        curr_a = float(df[col_a].iloc[idx])
        prev_a = float(df[col_a].iloc[idx - 1])
        curr_b = _val(df, idx, col_b_or_value)
        prev_b = _val(df, idx - 1, col_b_or_value)
        if not all(_safe(v) for v in [curr_a, prev_a, curr_b, prev_b]):
            return False
        return prev_a >= prev_b and curr_a < curr_b
    return _check


# ---------------------------------------------------------------------------
# Threshold / comparison conditions
# ---------------------------------------------------------------------------


def above(col: str, ref: Ref) -> ConditionFn:
    """True when col is above ref at current bar."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        v = float(df[col].iloc[idx])
        r = _val(df, idx, ref)
        return _safe(v) and _safe(r) and v > r
    return _check


def below(col: str, ref: Ref) -> ConditionFn:
    """True when col is below ref at current bar."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        v = float(df[col].iloc[idx])
        r = _val(df, idx, ref)
        return _safe(v) and _safe(r) and v < r
    return _check


# ---------------------------------------------------------------------------
# Directional / trend conditions
# ---------------------------------------------------------------------------


def rising(col: str, bars: int) -> ConditionFn:
    """True when col has been rising for the last `bars` bars."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < bars:
            return False
        vals = df[col].iloc[idx - bars: idx + 1]
        if vals.isna().any():
            return False
        for i in range(1, len(vals)):
            if vals.iloc[i] <= vals.iloc[i - 1]:
                return False
        return True
    return _check


def falling(col: str, bars: int) -> ConditionFn:
    """True when col has been falling for the last `bars` bars."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < bars:
            return False
        vals = df[col].iloc[idx - bars: idx + 1]
        if vals.isna().any():
            return False
        for i in range(1, len(vals)):
            if vals.iloc[i] >= vals.iloc[i - 1]:
                return False
        return True
    return _check


# ---------------------------------------------------------------------------
# Combinators
# ---------------------------------------------------------------------------


def all_of(*conditions: ConditionFn) -> ConditionFn:
    """True when all sub-conditions are True."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        return all(c(df, idx) for c in conditions)
    return _check


def any_of(*conditions: ConditionFn) -> ConditionFn:
    """True when at least one sub-condition is True."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        return any(c(df, idx) for c in conditions)
    return _check


# ---------------------------------------------------------------------------
# Pullback conditions
# ---------------------------------------------------------------------------


def pullback_to(level_col: str, tolerance_atr_mult: float = 0.5) -> ConditionFn:
    """True when price dips to level (within tolerance * ATR) and closes back above.

    Checks that low touched the level zone but close is above the level.
    """
    def _check(df: pd.DataFrame, idx: int) -> bool:
        low_val = float(df["low"].iloc[idx])
        close_val = float(df["close"].iloc[idx])
        level = float(df[level_col].iloc[idx])
        atr = float(df["atr_14"].iloc[idx])
        if not all(_safe(v) for v in [low_val, close_val, level, atr]):
            return False
        tolerance = tolerance_atr_mult * atr
        return (low_val <= level + tolerance) and (close_val > level)
    return _check


def pullback_below(level_col: str, tolerance_atr_mult: float = 0.5) -> ConditionFn:
    """True when price spikes to level (within tolerance * ATR) and closes back below.

    Mirror of pullback_to for short entries.
    """
    def _check(df: pd.DataFrame, idx: int) -> bool:
        high_val = float(df["high"].iloc[idx])
        close_val = float(df["close"].iloc[idx])
        level = float(df[level_col].iloc[idx])
        atr = float(df["atr_14"].iloc[idx])
        if not all(_safe(v) for v in [high_val, close_val, level, atr]):
            return False
        tolerance = tolerance_atr_mult * atr
        return (high_val >= level - tolerance) and (close_val < level)
    return _check


# ---------------------------------------------------------------------------
# Divergence conditions
# ---------------------------------------------------------------------------


def bullish_divergence(indicator_col: str, lookback: int = 5) -> ConditionFn:
    """Price makes lower low but indicator makes higher low."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < lookback:
            return False
        price_now = float(df["low"].iloc[idx])
        price_prev = float(df["low"].iloc[idx - lookback])
        ind_now = float(df[indicator_col].iloc[idx])
        ind_prev = float(df[indicator_col].iloc[idx - lookback])
        if not all(_safe(v) for v in [price_now, price_prev, ind_now, ind_prev]):
            return False
        return price_now < price_prev and ind_now > ind_prev
    return _check


def bearish_divergence(indicator_col: str, lookback: int = 5) -> ConditionFn:
    """Price makes higher high but indicator makes lower high."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < lookback:
            return False
        price_now = float(df["high"].iloc[idx])
        price_prev = float(df["high"].iloc[idx - lookback])
        ind_now = float(df[indicator_col].iloc[idx])
        ind_prev = float(df[indicator_col].iloc[idx - lookback])
        if not all(_safe(v) for v in [price_now, price_prev, ind_now, ind_prev]):
            return False
        return price_now > price_prev and ind_now < ind_prev
    return _check


# ---------------------------------------------------------------------------
# Candlestick pattern conditions
# ---------------------------------------------------------------------------


def candle_bullish(pattern_col: str) -> ConditionFn:
    """True when the candle pattern column signals bullish (> 0)."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        v = float(df[pattern_col].iloc[idx])
        return _safe(v) and v > 0
    return _check


def candle_bearish(pattern_col: str) -> ConditionFn:
    """True when the candle pattern column signals bearish (< 0)."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        v = float(df[pattern_col].iloc[idx])
        return _safe(v) and v < 0
    return _check


# ---------------------------------------------------------------------------
# Consecutive close conditions
# ---------------------------------------------------------------------------


def consecutive_higher_closes(count: int) -> ConditionFn:
    """True when the last `count` closes are each higher than the previous."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < count:
            return False
        closes = df["close"].iloc[idx - count: idx + 1]
        if closes.isna().any():
            return False
        for i in range(1, len(closes)):
            if closes.iloc[i] <= closes.iloc[i - 1]:
                return False
        return True
    return _check


def consecutive_lower_closes(count: int) -> ConditionFn:
    """True when the last `count` closes are each lower than the previous."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < count:
            return False
        closes = df["close"].iloc[idx - count: idx + 1]
        if closes.isna().any():
            return False
        for i in range(1, len(closes)):
            if closes.iloc[i] >= closes.iloc[i - 1]:
                return False
        return True
    return _check


# ---------------------------------------------------------------------------
# Volatility / range conditions
# ---------------------------------------------------------------------------


def squeeze(width_col: str, lookback: int = 50) -> ConditionFn:
    """True when width_col is at its lowest in the last `lookback` bars."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < lookback:
            return False
        window = df[width_col].iloc[idx - lookback + 1: idx + 1]
        if window.isna().any():
            return False
        return float(df[width_col].iloc[idx]) <= float(window.min())
    return _check


def range_exceeds_atr(multiplier: float) -> ConditionFn:
    """True when current bar range (high - low) exceeds multiplier * ATR."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        bar_range = float(df["high"].iloc[idx]) - float(df["low"].iloc[idx])
        atr = float(df["atr_14"].iloc[idx])
        return _safe(bar_range) and _safe(atr) and bar_range > multiplier * atr
    return _check


def narrowest_range(lookback: int = 7) -> ConditionFn:
    """True when current bar range is the smallest of last `lookback` bars."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < lookback - 1:
            return False
        ranges = (df["high"].iloc[idx - lookback + 1: idx + 1] - df["low"].iloc[idx - lookback + 1: idx + 1])
        if ranges.isna().any():
            return False
        curr_range = float(df["high"].iloc[idx]) - float(df["low"].iloc[idx])
        return curr_range <= float(ranges.min())
    return _check


# ---------------------------------------------------------------------------
# Breakout conditions
# ---------------------------------------------------------------------------


def breaks_above_level(level_col: str) -> ConditionFn:
    """True when close breaks above level_col at current bar."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < 1:
            return False
        close_now = float(df["close"].iloc[idx])
        close_prev = float(df["close"].iloc[idx - 1])
        level_now = float(df[level_col].iloc[idx])
        level_prev = float(df[level_col].iloc[idx - 1])
        if not all(_safe(v) for v in [close_now, close_prev, level_now, level_prev]):
            return False
        return close_prev <= level_prev and close_now > level_now
    return _check


def breaks_below_level(level_col: str) -> ConditionFn:
    """True when close breaks below level_col at current bar."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < 1:
            return False
        close_now = float(df["close"].iloc[idx])
        close_prev = float(df["close"].iloc[idx - 1])
        level_now = float(df[level_col].iloc[idx])
        level_prev = float(df[level_col].iloc[idx - 1])
        if not all(_safe(v) for v in [close_now, close_prev, level_now, level_prev]):
            return False
        return close_prev >= level_prev and close_now < level_now
    return _check


# ---------------------------------------------------------------------------
# Range position conditions
# ---------------------------------------------------------------------------


def in_top_pct_of_range(pct: float = 0.25) -> ConditionFn:
    """True when close is in the top `pct` (e.g., 0.25 = top 25%) of bar range."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        h = float(df["high"].iloc[idx])
        l = float(df["low"].iloc[idx])
        c = float(df["close"].iloc[idx])
        if not all(_safe(v) for v in [h, l, c]) or h == l:
            return False
        return (c - l) / (h - l) >= (1.0 - pct)
    return _check


def in_bottom_pct_of_range(pct: float = 0.25) -> ConditionFn:
    """True when close is in the bottom `pct` of bar range."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        h = float(df["high"].iloc[idx])
        l = float(df["low"].iloc[idx])
        c = float(df["close"].iloc[idx])
        if not all(_safe(v) for v in [h, l, c]) or h == l:
            return False
        return (c - l) / (h - l) <= pct
    return _check


# ---------------------------------------------------------------------------
# Gap conditions
# ---------------------------------------------------------------------------


def gap_up(atr_mult: float = 1.0) -> ConditionFn:
    """True when open gaps up more than atr_mult * ATR above prior close."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < 1:
            return False
        open_now = float(df["open"].iloc[idx])
        close_prev = float(df["close"].iloc[idx - 1])
        atr = float(df["atr_14"].iloc[idx])
        if not all(_safe(v) for v in [open_now, close_prev, atr]):
            return False
        return open_now > close_prev + atr_mult * atr
    return _check


def gap_down(atr_mult: float = 1.0) -> ConditionFn:
    """True when open gaps down more than atr_mult * ATR below prior close."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < 1:
            return False
        open_now = float(df["open"].iloc[idx])
        close_prev = float(df["close"].iloc[idx - 1])
        atr = float(df["atr_14"].iloc[idx])
        if not all(_safe(v) for v in [open_now, close_prev, atr]):
            return False
        return open_now < close_prev - atr_mult * atr
    return _check


# ---------------------------------------------------------------------------
# Deviation condition
# ---------------------------------------------------------------------------


def deviation_from(col: str, ref_col: str, atr_mult: float, direction: str = "below") -> ConditionFn:
    """True when col deviates from ref_col by more than atr_mult * ATR.

    Args:
        col: Column to check (e.g., "close")
        ref_col: Reference column (e.g., "ema_20")
        atr_mult: Multiple of ATR for the deviation threshold
        direction: "below" if col < ref (oversold), "above" if col > ref (overbought)
    """
    def _check(df: pd.DataFrame, idx: int) -> bool:
        v = float(df[col].iloc[idx])
        r = float(df[ref_col].iloc[idx])
        atr = float(df["atr_14"].iloc[idx])
        if not all(_safe(x) for x in [v, r, atr]):
            return False
        if direction == "below":
            return (r - v) > atr_mult * atr
        else:
            return (v - r) > atr_mult * atr
    return _check


# ---------------------------------------------------------------------------
# Holding / state conditions
# ---------------------------------------------------------------------------


def was_below_then_crosses_above(col: str, threshold: float, lookback: int = 5) -> ConditionFn:
    """True when col was below threshold within last `lookback` bars and now crosses above."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < lookback:
            return False
        curr = float(df[col].iloc[idx])
        prev = float(df[col].iloc[idx - 1])
        if not (_safe(curr) and _safe(prev)):
            return False
        # Must cross above now
        if not (prev <= threshold and curr > threshold):
            return False
        # Must have been below threshold within lookback
        window = df[col].iloc[idx - lookback: idx]
        return bool((window < threshold).any())
    return _check


def was_above_then_crosses_below(col: str, threshold: float, lookback: int = 5) -> ConditionFn:
    """True when col was above threshold within last `lookback` bars and now crosses below."""
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < lookback:
            return False
        curr = float(df[col].iloc[idx])
        prev = float(df[col].iloc[idx - 1])
        if not (_safe(curr) and _safe(prev)):
            return False
        if not (prev >= threshold and curr < threshold):
            return False
        window = df[col].iloc[idx - lookback: idx]
        return bool((window > threshold).any())
    return _check


def held_for_n_bars(col: str, condition_fn, n_bars: int) -> ConditionFn:
    """True when a sub-condition has been True for the last n_bars bars.

    Args:
        col: Not used directly, for documentation.
        condition_fn: A simple lambda (val) -> bool to check against col values.
        n_bars: Number of consecutive bars the condition must hold.
    """
    def _check(df: pd.DataFrame, idx: int) -> bool:
        if idx < n_bars - 1:
            return False
        for i in range(idx - n_bars + 1, idx + 1):
            val = float(df[col].iloc[i])
            if not _safe(val) or not condition_fn(val):
                return False
        return True
    return _check
