"""Unit tests for condition factory functions."""

import numpy as np
import pandas as pd
import pytest

from src.strats_prob.conditions import (
    above,
    all_of,
    any_of,
    below,
    breaks_above_level,
    breaks_below_level,
    bullish_divergence,
    bearish_divergence,
    candle_bullish,
    candle_bearish,
    consecutive_higher_closes,
    consecutive_lower_closes,
    crosses_above,
    crosses_below,
    deviation_from,
    falling,
    gap_down,
    gap_up,
    held_for_n_bars,
    in_bottom_pct_of_range,
    in_top_pct_of_range,
    narrowest_range,
    pullback_below,
    pullback_to,
    range_exceeds_atr,
    rising,
    squeeze,
    was_above_then_crosses_below,
    was_below_then_crosses_above,
)


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """DataFrame with known values for deterministic testing."""
    index = pd.date_range("2024-01-01", periods=10, freq="1h")
    return pd.DataFrame(
        {
            "close": [100, 101, 102, 103, 104, 103, 102, 101, 100, 99],
            "open": [99.5, 100.5, 101.5, 102.5, 103.5, 103.5, 102.5, 101.5, 100.5, 99.5],
            "high": [101, 102, 103, 104, 105, 104, 103, 102, 101, 100],
            "low": [99, 100, 101, 102, 103, 102, 101, 100, 99, 98],
            "volume": [1000] * 10,
            "ema_20": [99, 99.5, 100, 100.5, 101, 101.5, 102, 102.5, 103, 103.5],
            "ema_50": [100, 100, 100, 100, 100, 100, 100, 100, 100, 100],
            "atr_14": [1.0] * 10,
            "rsi_14": [30, 35, 40, 50, 60, 70, 65, 55, 45, 35],
            "indicator_a": [50, 48, 46, 44, 42, 44, 46, 48, 50, 52],
        },
        index=index,
    )


class TestCrossesAbove:
    """Tests for crosses_above condition."""

    def test_cross_column_vs_column(self, sample_df):
        """EMA20 crosses above EMA50 between bars 2-3."""
        cond = crosses_above("ema_20", "ema_50")
        # Bar 2: ema_20=100 == ema_50=100, bar 3: ema_20=100.5 > ema_50=100
        assert cond(sample_df, 3) is True

    def test_no_cross_when_already_above(self, sample_df):
        """No cross at bar 4 because already above."""
        cond = crosses_above("ema_20", "ema_50")
        assert cond(sample_df, 4) is False

    def test_cross_vs_fixed_value(self, sample_df):
        """Close crosses above fixed value 103 at bar 3."""
        cond = crosses_above("close", 103)
        # Bar 2: close=102, bar 3: close=103 (not >), so False
        assert cond(sample_df, 3) is False
        # Bar 3: close=103, bar 4: close=104 > 103
        assert cond(sample_df, 4) is True

    def test_idx_zero_returns_false(self, sample_df):
        cond = crosses_above("close", 50)
        assert cond(sample_df, 0) is False

    def test_nan_returns_false(self, sample_df):
        sample_df.loc[sample_df.index[3], "close"] = np.nan
        cond = crosses_above("close", 103)
        assert cond(sample_df, 3) is False


class TestCrossesBelow:
    """Tests for crosses_below condition."""

    def test_cross_below_fixed(self, sample_df):
        """Close crosses below 102 at bar 6 (103->102)."""
        cond = crosses_below("close", 103)
        # Bar 5: close=103 >= 103, bar 6: close=102 < 103
        assert cond(sample_df, 6) is True

    def test_no_cross_when_already_below(self, sample_df):
        cond = crosses_below("close", 103)
        # Bar 7: close=101 already below, bar 6 was cross
        assert cond(sample_df, 7) is False


class TestAboveBelow:
    """Tests for above and below conditions."""

    def test_above_column(self, sample_df):
        cond = above("close", "ema_50")
        assert cond(sample_df, 4) is True  # 104 > 100
        assert cond(sample_df, 0) is False  # 100 > 100 is False

    def test_above_fixed(self, sample_df):
        cond = above("close", 103.5)
        assert cond(sample_df, 4) is True
        assert cond(sample_df, 3) is False

    def test_below_column(self, sample_df):
        cond = below("close", "ema_20")
        assert cond(sample_df, 8) is True  # 100 < 103
        assert cond(sample_df, 4) is False  # 104 not < 101

    def test_below_fixed(self, sample_df):
        cond = below("rsi_14", 40)
        assert cond(sample_df, 0) is True  # 30 < 40
        assert cond(sample_df, 3) is False  # 50 not < 40


class TestRisingFalling:
    """Tests for rising and falling conditions."""

    def test_rising_3_bars(self, sample_df):
        """Close rises for 3 bars: 100->101->102->103 (bars 0-3)."""
        cond = rising("close", 3)
        assert cond(sample_df, 3) is True  # bars 0,1,2,3 all rising

    def test_rising_fails_on_flat(self, sample_df):
        cond = rising("ema_50", 2)
        assert cond(sample_df, 3) is False  # ema_50 is constant

    def test_falling_3_bars(self, sample_df):
        """Close falls for 3 bars: 103->102->101->100 (bars 5-8)."""
        cond = falling("close", 3)
        assert cond(sample_df, 8) is True

    def test_insufficient_bars(self, sample_df):
        cond = rising("close", 5)
        assert cond(sample_df, 3) is False  # idx=3 < bars=5


class TestCombinators:
    """Tests for all_of and any_of."""

    def test_all_of_true(self, sample_df):
        cond = all_of(above("close", 103), above("rsi_14", 55))
        assert cond(sample_df, 4) is True  # close=104>103, rsi=60>55

    def test_all_of_partial_false(self, sample_df):
        cond = all_of(above("close", 103), below("rsi_14", 55))
        assert cond(sample_df, 4) is False  # rsi=60 not < 55

    def test_any_of_one_true(self, sample_df):
        cond = any_of(above("close", 200), below("rsi_14", 35))
        assert cond(sample_df, 0) is True  # rsi=30 < 35

    def test_any_of_none_true(self, sample_df):
        cond = any_of(above("close", 200), below("rsi_14", 20))
        assert cond(sample_df, 0) is False


class TestPullback:
    """Tests for pullback_to and pullback_below."""

    def test_pullback_to_level(self, sample_df):
        """Low touches level within tolerance and close is above level."""
        cond = pullback_to("ema_20", tolerance_atr_mult=0.5)
        # Bar 0: low=99, ema_20=99, close=100 > 99, atr=1, tol=0.5
        # low(99) <= level(99)+0.5(100.5) => True; close(100) > level(99) => True
        assert cond(sample_df, 0) is True

    def test_pullback_below_level(self, sample_df):
        """High touches level within tolerance and close is below level."""
        cond = pullback_below("ema_20", tolerance_atr_mult=0.5)
        # Bar 8: high=101, ema_20=103, close=100, atr=1
        # high(101) >= level(103)-0.5(102.5) => False
        assert cond(sample_df, 8) is False


class TestDivergence:
    """Tests for bullish and bearish divergence."""

    def test_bullish_divergence(self, sample_df):
        """Price lower low but indicator higher low."""
        cond = bullish_divergence("indicator_a", lookback=5)
        # Bar 9: low=98, bar 4: low=103 => price_now(98) < price_prev(103) ✓
        # Bar 9: ind=52, bar 4: ind=42 => ind_now(52) > ind_prev(42) ✓
        assert cond(sample_df, 9) is True

    def test_bearish_divergence(self, sample_df):
        """Price higher high but indicator lower high."""
        cond = bearish_divergence("indicator_a", lookback=4)
        # Bar 4: high=105, bar 0: high=101 => price higher high ✓
        # Bar 4: ind=42, bar 0: ind=50 => ind lower ✓
        assert cond(sample_df, 4) is True

    def test_divergence_insufficient_bars(self, sample_df):
        cond = bullish_divergence("indicator_a", lookback=5)
        assert cond(sample_df, 3) is False


class TestCandlePatterns:
    """Tests for candle_bullish and candle_bearish."""

    def test_candle_bullish(self, sample_df):
        sample_df["cdl_engulfing"] = [0, 100, 0, 0, 0, 0, -100, 0, 0, 0]
        cond = candle_bullish("cdl_engulfing")
        assert cond(sample_df, 1) is True
        assert cond(sample_df, 0) is False
        assert cond(sample_df, 6) is False

    def test_candle_bearish(self, sample_df):
        sample_df["cdl_engulfing"] = [0, 100, 0, 0, 0, 0, -100, 0, 0, 0]
        cond = candle_bearish("cdl_engulfing")
        assert cond(sample_df, 6) is True
        assert cond(sample_df, 1) is False


class TestConsecutiveCloses:
    """Tests for consecutive_higher_closes and consecutive_lower_closes."""

    def test_higher_closes_3(self, sample_df):
        cond = consecutive_higher_closes(3)
        # Bars 0-3: 100,101,102,103 => 3 consecutive higher closes
        assert cond(sample_df, 3) is True

    def test_higher_closes_fails(self, sample_df):
        cond = consecutive_higher_closes(3)
        # Bars 3-6: 103,104,103,102 => NOT 3 higher
        assert cond(sample_df, 6) is False

    def test_lower_closes_3(self, sample_df):
        cond = consecutive_lower_closes(3)
        # Bars 5-8: 103,102,101,100 => 3 consecutive lower
        assert cond(sample_df, 8) is True

    def test_lower_closes_insufficient_bars(self, sample_df):
        cond = consecutive_lower_closes(5)
        assert cond(sample_df, 3) is False


class TestVolatilityConditions:
    """Tests for squeeze, range_exceeds_atr, narrowest_range."""

    def test_squeeze(self):
        index = pd.date_range("2024-01-01", periods=10, freq="1h")
        df = pd.DataFrame(
            {"bb_width": [5, 4, 3, 2, 1, 0.5, 0.4, 0.3, 0.2, 0.1]},
            index=index,
        )
        cond = squeeze("bb_width", lookback=5)
        # Bar 9: bb_width=0.1, lowest in bars 5-9 (0.5,0.4,0.3,0.2,0.1) => True
        assert cond(df, 9) is True
        # Bar 5: bb_width=0.5, lowest in bars 1-5 (4,3,2,1,0.5) => True
        assert cond(df, 5) is True

    def test_range_exceeds_atr(self, sample_df):
        """Bar range is 2.0, ATR=1.0, multiplier=1.5 => 2.0 > 1.5 => True."""
        cond = range_exceeds_atr(1.5)
        # All bars have high-low=2.0 and atr=1.0
        assert cond(sample_df, 4) is True

    def test_range_does_not_exceed(self, sample_df):
        cond = range_exceeds_atr(3.0)
        assert cond(sample_df, 4) is False

    def test_narrowest_range(self):
        index = pd.date_range("2024-01-01", periods=10, freq="1h")
        df = pd.DataFrame(
            {
                "high": [102, 103, 101.5, 101.2, 101.1, 100.5, 100.3, 100.2, 100.15, 100.1],
                "low": [100, 100, 100.5, 100.2, 100.1, 100.0, 100.0, 100.0, 100.05, 100.0],
            },
            index=index,
        )
        cond = narrowest_range(lookback=5)
        # Bar 9: range=0.1, bars 5-9 ranges: 0.5,0.3,0.2,0.1,0.1 => min=0.1 => True
        assert cond(df, 9) is True


class TestBreakoutConditions:
    """Tests for breaks_above_level and breaks_below_level."""

    def test_breaks_above(self, sample_df):
        """Close breaks above ema_50 between bars 0-1."""
        cond = breaks_above_level("ema_50")
        # Bar 0: close=100, ema_50=100 => close<=level
        # Bar 1: close=101, ema_50=100 => close>level, and prev was <=
        assert cond(sample_df, 1) is True

    def test_breaks_below(self, sample_df):
        """Close breaks below ema_20 at bar 8."""
        cond = breaks_below_level("ema_20")
        # Bar 7: close=101 < ema_20=102.5 => already below
        # Actually: bar 5: close=103 >= ema_20=101.5, bar 6: close=102 >= ema_20=102
        # bar 6: close=102 >= ema_20=102 (prev), bar 7: close=101 < ema_20=102.5
        assert cond(sample_df, 7) is True


class TestRangePosition:
    """Tests for in_top_pct_of_range and in_bottom_pct_of_range."""

    def test_in_top_25_pct(self, sample_df):
        """Close at top of range."""
        cond = in_top_pct_of_range(0.25)
        # Bar 4: high=105, low=103, close=104 => (104-103)/(105-103)=0.5 >= 0.75? No
        assert cond(sample_df, 4) is False
        # Bar 3: high=104, low=102, close=103 => (103-102)/(104-102)=0.5 >= 0.75? No
        assert cond(sample_df, 3) is False

    def test_in_top_60_pct(self, sample_df):
        """Close in top 60% of range."""
        cond = in_top_pct_of_range(0.60)
        # Bar 4: (104-103)/(105-103) = 0.5 >= 0.4? Yes
        assert cond(sample_df, 4) is True

    def test_in_bottom_25_pct(self, sample_df):
        """Close near bottom of range."""
        cond = in_bottom_pct_of_range(0.60)
        # Bar 4: (104-103)/(105-103) = 0.5 <= 0.6? Yes
        assert cond(sample_df, 4) is True


class TestGapConditions:
    """Tests for gap_up and gap_down."""

    def test_gap_up(self):
        index = pd.date_range("2024-01-01", periods=3, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100, 103, 104],
                "close": [101, 104, 105],
                "high": [102, 105, 106],
                "low": [99, 102, 103],
                "atr_14": [1.0, 1.0, 1.0],
            },
            index=index,
        )
        cond = gap_up(1.0)
        # Bar 1: open=103, prev close=101, atr=1 => 103 > 101+1=102 => True
        assert cond(df, 1) is True
        assert cond(df, 2) is False  # 104 not > 104+1=105

    def test_gap_down(self):
        index = pd.date_range("2024-01-01", periods=3, freq="1h")
        df = pd.DataFrame(
            {
                "open": [100, 97, 96],
                "close": [99, 96, 95],
                "high": [101, 98, 97],
                "low": [98, 95, 94],
                "atr_14": [1.0, 1.0, 1.0],
            },
            index=index,
        )
        cond = gap_down(1.0)
        # Bar 1: open=97, prev close=99, atr=1 => 97 < 99-1=98 => True
        assert cond(df, 1) is True


class TestDeviation:
    """Tests for deviation_from."""

    def test_deviation_below(self, sample_df):
        """Close below EMA by more than 2*ATR."""
        cond = deviation_from("close", "ema_20", atr_mult=2.0, direction="below")
        # Bar 9: close=99, ema_20=103.5, atr=1 => (103.5-99)=4.5 > 2*1=2 => True
        assert cond(sample_df, 9) is True

    def test_deviation_above(self, sample_df):
        cond = deviation_from("close", "ema_20", atr_mult=2.0, direction="above")
        # Bar 4: close=104, ema_20=101, atr=1 => (104-101)=3 > 2*1=2 => True
        assert cond(sample_df, 4) is True

    def test_deviation_not_enough(self, sample_df):
        cond = deviation_from("close", "ema_20", atr_mult=5.0, direction="below")
        # Bar 9: 4.5 > 5*1=5 => False
        assert cond(sample_df, 9) is False


class TestStateConditions:
    """Tests for was_below_then_crosses_above, was_above_then_crosses_below, held_for_n_bars."""

    def test_was_below_then_crosses_above(self, sample_df):
        # RSI values: [30, 35, 40, 50, 60, 70, 65, 55, 45, 35]
        # Use lookback=3 so the guard (idx < lookback) passes at bar 4
        cond = was_below_then_crosses_above("rsi_14", 50, lookback=3)
        # Bar 4: prev=rsi[3]=50 (<=50), curr=rsi[4]=60 (>50) => cross!
        # window = rsi[1:4] = [35, 40, 50], (window < 50).any() => True (35<50)
        assert cond(sample_df, 4) is True

    def test_was_below_then_crosses_above_insufficient_bars(self, sample_df):
        """Returns False when idx < lookback."""
        cond = was_below_then_crosses_above("rsi_14", 50, lookback=10)
        assert cond(sample_df, 4) is False

    def test_was_above_then_crosses_below(self, sample_df):
        cond = was_above_then_crosses_below("rsi_14", 50, lookback=5)
        # Bar 8: rsi=45, prev=55 (>=50), curr=45 (<50) => cross!
        # Was above 50 in lookback? bars 4-7: 60,70,65,55 => yes
        assert cond(sample_df, 8) is True

    def test_held_for_n_bars(self, sample_df):
        cond = held_for_n_bars("rsi_14", lambda v: v > 40, n_bars=3)
        # Bars 3-5: rsi=50,60,70 all >40 => True at bar 5
        assert cond(sample_df, 5) is True
        # Bars 0-2: rsi=30,35,40 => 30 not >40 => False at bar 2
        assert cond(sample_df, 2) is False
