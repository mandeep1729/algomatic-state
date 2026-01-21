"""Tests for intrabar structure features."""

import numpy as np
import pandas as pd
import pytest

from src.features.intrabar import IntrabarFeatureCalculator


class TestIntrabarFeatureCalculator:
    """Tests for IntrabarFeatureCalculator."""

    @pytest.fixture
    def calculator(self) -> IntrabarFeatureCalculator:
        return IntrabarFeatureCalculator()

    def test_feature_specs(self, calculator: IntrabarFeatureCalculator):
        """Test that feature specs are properly defined."""
        specs = calculator.feature_specs
        assert len(specs) == 4
        names = [s.name for s in specs]
        assert "clv" in names
        assert "body_ratio" in names
        assert "upper_wick" in names
        assert "lower_wick" in names

    def test_output_columns(self, calculator: IntrabarFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that compute returns expected columns."""
        result = calculator.compute(ohlcv_df)
        assert list(result.columns) == ["clv", "body_ratio", "upper_wick", "lower_wick"]
        assert len(result) == len(ohlcv_df)

    def test_clv_range(self, calculator: IntrabarFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that CLV is in [0, 1] range."""
        result = calculator.compute(ohlcv_df)
        assert result["clv"].min() >= 0
        assert result["clv"].max() <= 1

    def test_body_ratio_range(self, calculator: IntrabarFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that body_ratio is in [0, 1] range."""
        result = calculator.compute(ohlcv_df)
        assert result["body_ratio"].min() >= 0
        assert result["body_ratio"].max() <= 1

    def test_wick_ratios_range(self, calculator: IntrabarFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that wick ratios are in [0, 1] range."""
        result = calculator.compute(ohlcv_df)
        assert result["upper_wick"].min() >= -1e-9  # Allow small numerical error
        assert result["upper_wick"].max() <= 1 + 1e-9
        assert result["lower_wick"].min() >= -1e-9
        assert result["lower_wick"].max() <= 1 + 1e-9

    def test_clv_calculation(self):
        """Test CLV calculation with known values."""
        calc = IntrabarFeatureCalculator()
        df = pd.DataFrame(
            {
                "open": [100.0],
                "high": [102.0],
                "low": [98.0],
                "close": [101.0],  # Close is 3/4 of the way up
            },
            index=pd.date_range("2024-01-01", periods=1, freq="1min"),
        )
        result = calc.compute(df)
        # CLV = (101 - 98) / (102 - 98) = 3/4 = 0.75
        assert np.isclose(result["clv"].iloc[0], 0.75, atol=1e-6)

    def test_body_ratio_bullish_bar(self):
        """Test body_ratio with a bullish bar."""
        calc = IntrabarFeatureCalculator()
        df = pd.DataFrame(
            {
                "open": [99.0],
                "high": [102.0],
                "low": [98.0],
                "close": [101.0],  # Body is 2 (101-99), range is 4 (102-98)
            },
            index=pd.date_range("2024-01-01", periods=1, freq="1min"),
        )
        result = calc.compute(df)
        # body_ratio = |101 - 99| / (102 - 98) = 2/4 = 0.5
        assert np.isclose(result["body_ratio"].iloc[0], 0.5, atol=1e-6)

    def test_upper_wick_calculation(self):
        """Test upper wick calculation."""
        calc = IntrabarFeatureCalculator()
        df = pd.DataFrame(
            {
                "open": [99.0],
                "high": [104.0],  # 3 above max(open, close)
                "low": [98.0],
                "close": [101.0],
            },
            index=pd.date_range("2024-01-01", periods=1, freq="1min"),
        )
        result = calc.compute(df)
        # upper_wick = (104 - 101) / (104 - 98) = 3/6 = 0.5
        assert np.isclose(result["upper_wick"].iloc[0], 0.5, atol=1e-6)

    def test_lower_wick_calculation(self):
        """Test lower wick calculation."""
        calc = IntrabarFeatureCalculator()
        df = pd.DataFrame(
            {
                "open": [101.0],
                "high": [104.0],
                "low": [97.0],  # 2 below min(open, close)
                "close": [99.0],
            },
            index=pd.date_range("2024-01-01", periods=1, freq="1min"),
        )
        result = calc.compute(df)
        # lower_wick = (99 - 97) / (104 - 97) = 2/7
        assert np.isclose(result["lower_wick"].iloc[0], 2 / 7, atol=1e-6)

    def test_no_nan_values(self, calculator: IntrabarFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that there are no NaN values (no lookback required)."""
        result = calculator.compute(ohlcv_df)
        assert not result.isna().any().any()
