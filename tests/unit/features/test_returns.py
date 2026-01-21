
"""Tests for Returns and Trend features."""

import numpy as np
import pandas as pd
import pytest

from src.features.returns import ReturnFeatureCalculator


class TestReturnFeatureCalculator:
    """Tests for ReturnFeatureCalculator."""

    @pytest.fixture
    def calculator(self) -> ReturnFeatureCalculator:
        return ReturnFeatureCalculator()

    def test_feature_specs(self, calculator: ReturnFeatureCalculator):
        """Test that feature specs are properly defined."""
        specs = calculator.feature_specs
        names = [s.name for s in specs]
        expected_names = [
            "r1", "r5", "r15", "r60",
            "cumret_60", "ema_diff", "slope_60", "trend_strength"
        ]
        for name in expected_names:
            assert name in names
    
    def test_output_columns(self, calculator: ReturnFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that compute returns expected columns."""
        result = calculator.compute(ohlcv_df)
        expected_columns = [
            "r1", "r5", "r15", "r60",
            "cumret_60", "ema_diff", "slope_60", "trend_strength"
        ]
        assert list(result.columns) == expected_columns
        assert len(result) == len(ohlcv_df)

    def test_r1_calculation(self):
        """Test r1 (1-bar log return) calculation."""
        calc = ReturnFeatureCalculator()
        df = pd.DataFrame(
            {"close": [100.0, 101.0, 102.0]},
            index=pd.date_range("2024-01-01", periods=3, freq="1min")
        )
        result = calc.compute(df)
        
        # r1[1] = log(101/100) approx 0.00995
        assert np.isclose(result["r1"].iloc[1], np.log(101/100), atol=1e-6)
        # r1[2] = log(102/101) approx 0.00985
        assert np.isclose(result["r1"].iloc[2], np.log(102/101), atol=1e-6)
        # r1[0] should be NaN
        assert np.isnan(result["r1"].iloc[0])

    def test_r5_calculation(self):
        """Test r5 (5-bar log return) calculation."""
        calc = ReturnFeatureCalculator(short_window=2) # Use smaller window for easier testing
        df = pd.DataFrame(
            {"close": [100.0, 101.0, 102.0, 103.0]},
            index=pd.date_range("2024-01-01", periods=4, freq="1min")
        )
        result = calc.compute(df)
        
        # r5 (which is r2 here) at index 2 = log(102/100)
        assert np.isclose(result["r5"].iloc[2], np.log(102/100), atol=1e-6)
        # r5 at index 3 = log(103/101)
        assert np.isclose(result["r5"].iloc[3], np.log(103/101), atol=1e-6)

    def test_cumret_60_calculation(self):
        """Test cumulative return calculation."""
        # Use small window for testing
        calc = ReturnFeatureCalculator(long_window=3)
        df = pd.DataFrame(
            {"close": [100.0, 101.0, 102.0, 101.0, 103.0]},
            index=pd.date_range("2024-01-01", periods=5, freq="1min")
        )
        result = calc.compute(df)
        
        # cumret_60 (window=3) is sum of last 3 r1s
        # r1s: [NaN, log(1.01), log(1.0099), log(0.99), log(1.0198)]
        # cumret at idx 3: r1[1] + r1[2] + r1[3] 
        # = log(101/100) + log(102/101) + log(101/102) = log(101/100)
        r1s = np.log(df["close"] / df["close"].shift(1))
        expected_sum = r1s.iloc[1] + r1s.iloc[2] + r1s.iloc[3]
        
        assert np.isclose(result["cumret_60"].iloc[3], expected_sum, atol=1e-6)

    def test_ema_diff_calculation(self):
        """Test EMA difference calculation."""
        calc = ReturnFeatureCalculator(ema_fast=2, ema_slow=4)
        df = pd.DataFrame(
            {"close": [100.0] * 10}, # Constant price
            index=pd.date_range("2024-01-01", periods=10, freq="1min")
        )
        result = calc.compute(df)
        
        # If price is constant, EMAs should be equal to price, diff should be 0
        assert np.allclose(result["ema_diff"].iloc[5:], 0.0, atol=1e-6)

    def test_trend_strength_calculation(self):
        """Test trend strength calculation."""
        # If slope is positive and vol is 1, strength should be abs(slope)
        calc = ReturnFeatureCalculator(long_window=5)
        df = pd.DataFrame(
            {"close": np.exp(np.linspace(0, 1, 10))}, # Exponential growth -> linear log price
            index=pd.date_range("2024-01-01", periods=10, freq="1min")
        )
        
        # Feed in known volatility
        rv_60 = pd.Series([0.1] * 10, index=df.index)
        result = calc.compute(df, rv_60=rv_60)
        
        # Slope of log(e^x) = slope of x = 1/(10-1) approx 0.111 per step if x goes 0 to 1 in 10 steps?
        # x = [0, 0.11, 0.22, ...]
        # slope should be constant
        
        # trend_strength = |slope| / rv
        assert not result["trend_strength"].isna().all()
        # Check non-NaN values are positive
        valid_strength = result["trend_strength"].dropna()
        assert (valid_strength >= 0).all()

    def test_pass_rv_60_kwarg(self, calculator: ReturnFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that passing rv_60 via kwargs works."""
        # Compute rv_60 separately
        r1 = np.log(ohlcv_df["close"] / ohlcv_df["close"].shift(1))
        rv_60 = r1.rolling(window=60).std()
        
        result = calculator.compute(ohlcv_df, rv_60=rv_60)
        assert "trend_strength" in result.columns
        assert not result["trend_strength"].isna().all()

