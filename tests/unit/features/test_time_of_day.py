
"""Tests for Time-of-Day features."""

import numpy as np
import pandas as pd
import pytest

from src.features.time_of_day import TimeOfDayFeatureCalculator


class TestTimeOfDayFeatureCalculator:
    """Tests for TimeOfDayFeatureCalculator."""

    @pytest.fixture
    def calculator(self) -> TimeOfDayFeatureCalculator:
        return TimeOfDayFeatureCalculator()

    def test_feature_specs(self, calculator: TimeOfDayFeatureCalculator):
        """Test that feature specs are properly defined."""
        specs = calculator.feature_specs
        names = [s.name for s in specs]
        expected_names = [
            "tod_sin", "tod_cos", "is_open_window",
            "is_close_window", "is_midday"
        ]
        for name in expected_names:
            assert name in names

    def test_output_columns(self, calculator: TimeOfDayFeatureCalculator, ohlcv_df: pd.DataFrame):
        """Test that compute returns expected columns."""
        result = calculator.compute(ohlcv_df)
        expected_columns = [
            "tod_sin", "tod_cos", "is_open_window",
            "is_close_window", "is_midday"
        ]
        assert list(result.columns) == expected_columns
        assert len(result) == len(ohlcv_df)

    def test_tod_calculation(self):
        """Test time-of-day calculation."""
        # 09:30 -> 0 minutes from open
        # 16:00 -> 390 minutes from open
        
        calc = TimeOfDayFeatureCalculator()
        
        dates = [
            "2024-01-01 09:30:00",
            "2024-01-01 12:00:00", # 2.5 hours = 150 mins
            "2024-01-01 16:00:00"
        ]
        df = pd.DataFrame(index=pd.to_datetime(dates))
        
        result = calc.compute(df)
        
        # Check tod_sin/cos
        # 09:30: norm=0, sin(0)=0, cos(0)=1
        assert np.isclose(result["tod_sin"].iloc[0], 0.0, atol=1e-6)
        assert np.isclose(result["tod_cos"].iloc[0], 1.0, atol=1e-6)
        
        # 16:00: norm=1, sin(2pi)=0, cos(2pi)=1
        assert np.isclose(result["tod_sin"].iloc[2], 0.0, atol=1e-6)
        assert np.isclose(result["tod_cos"].iloc[2], 1.0, atol=1e-6)

    def test_session_flags(self):
        """Test session window flags."""
        calc = TimeOfDayFeatureCalculator(
            open_window_minutes=30,
            close_window_minutes=60,
            midday_start_minutes=120,
            midday_end_minutes=240
        )
        
        dates = [
            "2024-01-01 09:40:00", # Open window (10 mins)
            "2024-01-01 12:30:00", # Midday (180 mins)
            "2024-01-01 15:30:00"  # Close window (360 mins, > 330)
        ]
        df = pd.DataFrame(index=pd.to_datetime(dates))
        
        result = calc.compute(df)
        
        assert result["is_open_window"].iloc[0] == 1
        assert result["is_midday"].iloc[0] == 0
        assert result["is_close_window"].iloc[0] == 0
        
        assert result["is_midday"].iloc[1] == 1
        
        # Close threshold is 390 - 60 = 330. 15:30 is 6 hours from 9:30 = 360 mins. 360 > 330.
        assert result["is_close_window"].iloc[2] == 1

