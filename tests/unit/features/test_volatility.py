
"""Tests for Volatility and Range features."""

import numpy as np
import pandas as pd
import pytest

from src.features.volatility import VolatilityFeatureCalculator


class TestVolatilityFeatureCalculator:
    """Tests for VolatilityFeatureCalculator."""

    @pytest.fixture
    def calculator(self) -> VolatilityFeatureCalculator:
        return VolatilityFeatureCalculator()

    def test_feature_specs(self, calculator: VolatilityFeatureCalculator):
        """Test that feature specs are properly defined."""
        specs = calculator.feature_specs
        names = [s.name for s in specs]
        expected_names = [
            "rv_15", "rv_60", "range_1", "atr_60", "range_z_60", "vol_of_vol"
        ]
        for name in expected_names:
            assert name in names

    def test_output_columns(self, calculator: VolatilityFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that compute returns expected columns."""
        result = calculator.compute(ohlcv_df)
        expected_columns = [
            "rv_15", "rv_60", "range_1", "atr_60", "range_z_60", "vol_of_vol"
        ]
        assert list(result.columns) == expected_columns
        assert len(result) == len(ohlcv_df)

    def test_range_1_calculation(self):
        """Test normalized range calculation."""
        calc = VolatilityFeatureCalculator()
        df = pd.DataFrame(
            {
                "high": [105.0],
                "low": [95.0],
                "close": [100.0],
            },
            index=pd.date_range("2024-01-01", periods=1, freq="1min")
        )
        result = calc.compute(df)
        # range_1 = (105 - 95) / 100 = 10 / 100 = 0.1
        assert np.isclose(result["range_1"].iloc[0], 0.1, atol=1e-6)

    def test_rv_calculation(self):
        """Test realized volatility calculation."""
        # Use small window for testing
        calc = VolatilityFeatureCalculator(short_window=3)
        df = pd.DataFrame(
            {
                "close": [100.0, 101.0, 100.0, 101.0, 100.0],
                "high": [102.0, 102.0, 102.0, 102.0, 102.0],
                "low": [98.0, 98.0, 98.0, 98.0, 98.0]
            },
            index=pd.date_range("2024-01-01", periods=5, freq="1min")
        )
        # r1: [NaN, 0.01, -0.01, 0.01, -0.01] approx
        # std of [0.01, -0.01, 0.01] -> non-zero
        
        result = calc.compute(df)
        assert not result["rv_15"].isna().all()
        assert result["rv_15"].iloc[-1] > 0

    def test_atr_60_calculation(self):
        """Test average range calculation."""
        calc = VolatilityFeatureCalculator(long_window=3)
        df = pd.DataFrame(
            {
                "high": [102.0, 102.0, 102.0, 102.0],
                "low": [98.0, 98.0, 98.0, 98.0],
                "close": [100.0, 100.0, 100.0, 100.0],
            },
            index=pd.date_range("2024-01-01", periods=4, freq="1min")
        )
        # range_1 is always (102-98)/100 = 0.04
        # mean of 0.04 is 0.04
        result = calc.compute(df)
        assert np.isclose(result["atr_60"].iloc[-1], 0.04, atol=1e-6)

    def test_vol_of_vol_calculation(self):
        """Test volatility of volatility."""
        # Need enough data for rv_15 window AND vol_of_vol window
        # rv_15 window = 2, vol_of_vol window (long) = 3
        calc = VolatilityFeatureCalculator(short_window=2, long_window=3)
        
        # Create data where volatility changes
        # First part low vol, second part high vol
        part1 = np.ones(10) * 100
        part2 = 100 + np.random.randn(10) # Noisier
        close = np.concatenate([part1, part2])
        
        df = pd.DataFrame(
            {"close": close, "high": close+1, "low": close-1},
            index=pd.date_range("2024-01-01", periods=20, freq="1min")
        )
        
        result = calc.compute(df)
        # Should be defined at the end
        assert not np.isnan(result["vol_of_vol"].iloc[-1])

    def test_pass_r1_kwarg(self, calculator: VolatilityFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that passing r1 via kwargs works."""
        r1 = np.log(ohlcv_df["close"] / ohlcv_df["close"].shift(1))
        result = calculator.compute(ohlcv_df, r1=r1)
        assert "rv_15" in result.columns
        assert not result["rv_15"].isna().all()
