
"""Tests for Volume and Participation features."""

import numpy as np
import pandas as pd
import pytest

from src.features.volume import VolumeFeatureCalculator


class TestVolumeFeatureCalculator:
    """Tests for VolumeFeatureCalculator."""

    @pytest.fixture
    def calculator(self) -> VolumeFeatureCalculator:
        return VolumeFeatureCalculator()

    def test_feature_specs(self, calculator: VolumeFeatureCalculator):
        """Test that feature specs are properly defined."""
        specs = calculator.feature_specs
        names = [s.name for s in specs]
        expected_names = [
            "vol1", "dvol1", "relvol_60", "vol_z_60", "dvol_z_60"
        ]
        for name in expected_names:
            assert name in names

    def test_output_columns(self, calculator: VolumeFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that compute returns expected columns."""
        result = calculator.compute(ohlcv_df)
        expected_columns = [
            "vol1", "dvol1", "relvol_60", "vol_z_60", "dvol_z_60"
        ]
        assert list(result.columns) == expected_columns
        assert len(result) == len(ohlcv_df)

    def test_vol1_calculation(self):
        """Test raw volume calculation."""
        calc = VolumeFeatureCalculator()
        df = pd.DataFrame(
            {"volume": [100, 200, 300], "close": [10.0, 10.0, 10.0]},
            index=pd.date_range("2024-01-01", periods=3, freq="1min")
        )
        result = calc.compute(df)
        assert np.array_equal(result["vol1"].values, [100, 200, 300])

    def test_dvol1_calculation(self):
        """Test dollar volume calculation."""
        calc = VolumeFeatureCalculator()
        df = pd.DataFrame(
            {"volume": [100, 200], "close": [10.0, 20.0]},
            index=pd.date_range("2024-01-01", periods=2, freq="1min")
        )
        result = calc.compute(df)
        # dvol = 100*10=1000, 200*20=4000
        assert np.array_equal(result["dvol1"].values, [1000.0, 4000.0])

    def test_relvol_calculation(self):
        """Test relative volume calculation."""
        calc = VolumeFeatureCalculator(window=3)
        df = pd.DataFrame(
            {"volume": [100, 100, 100, 200], "close": [10.0]*4},
            index=pd.date_range("2024-01-01", periods=4, freq="1min")
        )
        result = calc.compute(df)
        # At index 2 (3rd bar): mean(100, 100, 100) = 100. relvol = 100/100 = 1.0
        assert np.isclose(result["relvol_60"].iloc[2], 1.0, atol=1e-6)
        
        # At index 3 (4th bar): mean(100, 100, 200) = 133.33. relvol = 200/133.33 = 1.5
        assert np.isclose(result["relvol_60"].iloc[3], 1.5, atol=1e-6)

    def test_zscore_calculation(self):
        """Test z-score calculation."""
        calc = VolumeFeatureCalculator(window=3)
        df = pd.DataFrame(
            {"volume": [100, 110, 90, 200], "close": [10.0]*4},
            index=pd.date_range("2024-01-01", periods=4, freq="1min")
        )
        # Z-score of volume
        result = calc.compute(df)
        assert not np.isnan(result["vol_z_60"].iloc[-1])
