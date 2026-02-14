"""Parity tests for Python/Go strategy condition functions.

Verifies that Python conditions (src/strats_prob/conditions.py) produce
identical results to their Go counterparts (go-strats/pkg/conditions/).
"""

import numpy as np
import pandas as pd
import pytest

from src.strats_prob.conditions import (
    above,
    below,
    crosses_above,
    crosses_below,
    rising,
    falling,
)


def _make_df(col_values: dict, n: int = 20) -> pd.DataFrame:
    """Create a minimal DataFrame with specified column values."""
    index = pd.date_range("2024-06-03 09:30:00", periods=n, freq="1h")
    data = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000}
    data.update(col_values)
    return pd.DataFrame(data, index=index)


class TestRisingFallingParity:
    """Verify rising() and falling() implement strict monotonic checks.

    The Go Rising() function (conditions.go:161) was fixed to match
    Python's strict monotonic implementation. These tests pin the
    contract so any future divergence is caught immediately.
    """

    def test_rising_strictly_monotonic(self):
        """rising(col, 3) requires col[i-2] < col[i-1] < col[i]."""
        df = _make_df({"bb_width": [1.0, 2.0, 3.0, 4.0, 5.0, 4.0] + [3.0] * 14})
        check = rising("bb_width", 3)

        # idx=3: vals=[2,3,4] → all increasing → True
        assert check(df, 3) is True
        # idx=4: vals=[3,4,5] → all increasing → True
        assert check(df, 4) is True
        # idx=5: vals=[4,5,4] → 5→4 not increasing → False
        assert check(df, 5) is False

    def test_rising_requires_strict_increase(self):
        """Equal values should fail the strict monotonic check."""
        df = _make_df({"col": [1.0, 2.0, 3.0, 3.0, 4.0] + [0.0] * 15})
        check = rising("col", 3)

        # idx=3: vals=[2,3,3] → 3==3 not strictly increasing → False
        assert check(df, 3) is False
        # idx=4: vals=[3,3,4] → 3==3 not strictly increasing → False
        assert check(df, 4) is False

    def test_rising_with_nan_returns_false(self):
        """NaN in the window should return False."""
        df = _make_df({"col": [1.0, np.nan, 3.0, 4.0] + [0.0] * 16})
        check = rising("col", 3)

        # idx=3: vals=[nan, 3, 4] → has NaN → False
        assert check(df, 3) is False

    def test_rising_insufficient_bars(self):
        """Index below `bars` should return False."""
        df = _make_df({"col": [1.0, 2.0, 3.0] + [0.0] * 17})
        check = rising("col", 3)

        assert check(df, 0) is False
        assert check(df, 1) is False
        assert check(df, 2) is False

    def test_falling_strictly_monotonic(self):
        """falling(col, 3) requires col[i-2] > col[i-1] > col[i]."""
        df = _make_df({"col": [5.0, 4.0, 3.0, 2.0, 1.0] + [0.0] * 15})
        check = falling("col", 3)

        assert check(df, 3) is True  # vals=[4,3,2]
        assert check(df, 4) is True  # vals=[3,2,1]

    def test_falling_equal_values_fail(self):
        """Equal values should fail strict decrease."""
        df = _make_df({"col": [5.0, 4.0, 4.0, 3.0] + [0.0] * 16})
        check = falling("col", 3)

        assert check(df, 3) is False  # vals=[4,4,3]


class TestCrossConditionsParity:
    """Verify cross conditions match Go implementations."""

    def test_crosses_above(self):
        """crosses_above: fast was below slow, now fast >= slow."""
        df = _make_df({
            "fast": [10.0, 10.0, 10.0, 11.0] + [11.0] * 16,
            "slow": [11.0, 11.0, 11.0, 10.0] + [10.0] * 16,
        })
        check = crosses_above("fast", "slow")

        assert check(df, 2) is False  # fast < slow
        assert check(df, 3) is True   # fast crossed above slow

    def test_crosses_below(self):
        """crosses_below: fast was above slow, now fast <= slow."""
        df = _make_df({
            "fast": [11.0, 11.0, 11.0, 10.0] + [10.0] * 16,
            "slow": [10.0, 10.0, 10.0, 11.0] + [11.0] * 16,
        })
        check = crosses_below("fast", "slow")

        assert check(df, 2) is False
        assert check(df, 3) is True


class TestAboveBelowParity:
    """Verify above/below conditions."""

    def test_above(self):
        df = _make_df({"a": [5.0] * 20, "b": [3.0] * 20})
        assert above("a", "b")(df, 0) is True
        assert above("b", "a")(df, 0) is False

    def test_below(self):
        df = _make_df({"a": [3.0] * 20, "b": [5.0] * 20})
        assert below("a", "b")(df, 0) is True
        assert below("b", "a")(df, 0) is False

    def test_above_with_threshold(self):
        """above(col, threshold) compares column against a constant."""
        df = _make_df({"rsi_14": [55.0] * 20})
        assert above("rsi_14", 50)(df, 0) is True
        assert above("rsi_14", 60)(df, 0) is False
