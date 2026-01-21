
"""Tests for Anchor and Location features."""

import numpy as np
import pandas as pd
import pytest

from src.features.anchor import AnchorFeatureCalculator


class TestAnchorFeatureCalculator:
    """Tests for AnchorFeatureCalculator."""

    @pytest.fixture
    def calculator(self) -> AnchorFeatureCalculator:
        return AnchorFeatureCalculator()

    def test_feature_specs(self, calculator: AnchorFeatureCalculator):
        """Test that feature specs are properly defined."""
        specs = calculator.feature_specs
        names = [s.name for s in specs]
        expected_names = [
            "vwap_60", "dist_vwap_60", "dist_ema_48",
            "breakout_20", "pullback_depth"
        ]
        for name in expected_names:
            assert name in names

    def test_output_columns(self, calculator: AnchorFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that compute returns expected columns."""
        result = calculator.compute(ohlcv_df)
        expected_columns = [
            "vwap_60", "dist_vwap_60", "dist_ema_48",
            "breakout_20", "pullback_depth"
        ]
        assert list(result.columns) == expected_columns
        assert len(result) == len(ohlcv_df)

    def test_vwap_calculation(self):
        """Test VWAP calculation."""
        calc = AnchorFeatureCalculator(vwap_window=3)
        df = pd.DataFrame(
            {
                "high": [10.0, 10.0, 10.0],
                "low": [10.0, 10.0, 10.0],
                "close": [10.0, 10.0, 10.0], # TP = 10
                "volume": [100, 200, 300],
            },
            index=pd.date_range("2024-01-01", periods=3, freq="1min")
        )
        result = calc.compute(df)
        
        # All TP are 10. VWAP should be 10.
        assert np.isclose(result["vwap_60"].iloc[-1], 10.0, atol=1e-6)
        
        # Test with varying prices
        df2 = pd.DataFrame(
            {
                "high": [10.0, 20.0],
                "low": [10.0, 20.0],
                "close": [10.0, 20.0], # TP = 10, 20
                "volume": [100, 100],
            },
            index=pd.date_range("2024-01-01", periods=2, freq="1min")
        )
        calc2 = AnchorFeatureCalculator(vwap_window=2)
        result2 = calc2.compute(df2)
        # VWAP = (10*100 + 20*100) / (100+100) = 3000/200 = 15
        assert np.isclose(result2["vwap_60"].iloc[-1], 15.0, atol=1e-6)

    def test_dist_vwap_calculation(self):
        """Test distance from VWAP."""
        calc = AnchorFeatureCalculator(vwap_window=2)
        df = pd.DataFrame(
            {
                "high": [10.0, 10.0], "low": [10.0, 10.0], "close": [10.0, 10.0],
                "volume": [100, 100]
            },
            index=pd.date_range("2024-01-01", periods=2, freq="1min")
        )
        result = calc.compute(df)
        # Price = VWAP = 10. Dist should be 0.
        assert np.isclose(result["dist_vwap_60"].iloc[-1], 0.0, atol=1e-6)

    def test_breakout_pullback_calculation(self):
        """Test breakout and pullback calculations."""
        calc = AnchorFeatureCalculator(breakout_window=3)
        df = pd.DataFrame(
            {
                "high": [100.0, 105.0, 102.0],
                "low": [90.0, 95.0, 98.0],
                "close": [95.0, 100.0, 101.0],
                "volume": [100, 100, 100]
            },
            index=pd.date_range("2024-01-01", periods=3, freq="1min")
        )
        result = calc.compute(df)
        
        # Rolling high (window 3) at idx 2: max(100, 105, 102) = 105
        # Close at idx 2: 101
        
        # Breakout: (101 - 105) / 101 = -4 / 101
        expected_breakout = (101 - 105) / 101
        assert np.isclose(result["breakout_20"].iloc[2], expected_breakout, atol=1e-6)
        
        # Pullback depth: (105 - 101) / 105 = 4 / 105
        expected_pullback = (105 - 101) / 105
        assert np.isclose(result["pullback_depth"].iloc[2], expected_pullback, atol=1e-6)

