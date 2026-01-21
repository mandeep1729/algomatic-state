"""Time-of-day encoding features."""

from typing import Any

import numpy as np
import pandas as pd

from .base import BaseFeatureCalculator, FeatureSpec


class TimeOfDayFeatureCalculator(BaseFeatureCalculator):
    """Computes time-of-day encoding features.

    Features:
        - tod_sin: Sine encoding of time (cyclical)
        - tod_cos: Cosine encoding of time (cyclical)
        - is_open_window: Binary flag for first 30 minutes
        - is_close_window: Binary flag for last 60 minutes
        - is_midday: Binary flag for midday period

    Assumes RTH (Regular Trading Hours): 09:30-16:00 US/Eastern (390 minutes).
    """

    def __init__(
        self,
        market_open_hour: int = 9,
        market_open_minute: int = 30,
        trading_minutes: int = 390,
        open_window_minutes: int = 30,
        close_window_minutes: int = 60,
        midday_start_minutes: int = 120,
        midday_end_minutes: int = 240,
    ):
        """Initialize TimeOfDayFeatureCalculator.

        Args:
            market_open_hour: Market open hour (default 9 for 9:30 AM)
            market_open_minute: Market open minute (default 30)
            trading_minutes: Total trading minutes in day (default 390)
            open_window_minutes: Minutes to flag as open window (default 30)
            close_window_minutes: Minutes before close to flag (default 60)
            midday_start_minutes: Start of midday period from open (default 120)
            midday_end_minutes: End of midday period from open (default 240)
        """
        self.market_open_hour = market_open_hour
        self.market_open_minute = market_open_minute
        self.trading_minutes = trading_minutes
        self.open_window_minutes = open_window_minutes
        self.close_window_minutes = close_window_minutes
        self.midday_start_minutes = midday_start_minutes
        self.midday_end_minutes = midday_end_minutes

    @property
    def feature_specs(self) -> list[FeatureSpec]:
        return [
            FeatureSpec(
                name="tod_sin",
                description="Sine encoding of time-of-day",
                lookback=1,
                group="time_of_day",
            ),
            FeatureSpec(
                name="tod_cos",
                description="Cosine encoding of time-of-day",
                lookback=1,
                group="time_of_day",
            ),
            FeatureSpec(
                name="is_open_window",
                description="Binary: 1 if in first 30 minutes of trading",
                lookback=1,
                group="time_of_day",
            ),
            FeatureSpec(
                name="is_close_window",
                description="Binary: 1 if in last 60 minutes of trading",
                lookback=1,
                group="time_of_day",
            ),
            FeatureSpec(
                name="is_midday",
                description="Binary: 1 if in midday period (120-240 min from open)",
                lookback=1,
                group="time_of_day",
            ),
        ]

    def _compute_minutes_from_open(self, index: pd.DatetimeIndex) -> pd.Series:
        """Compute minutes elapsed since market open.

        Args:
            index: DatetimeIndex of the data

        Returns:
            Series of minutes since market open
        """
        # Extract hour and minute from index
        hours = index.hour
        minutes = index.minute

        # Compute total minutes since midnight
        total_minutes = hours * 60 + minutes

        # Compute market open in minutes since midnight
        market_open_total = self.market_open_hour * 60 + self.market_open_minute

        # Minutes since market open
        minutes_from_open = total_minutes - market_open_total

        return pd.Series(minutes_from_open, index=index)

    def compute(self, df: pd.DataFrame, **kwargs: Any) -> pd.DataFrame:
        """Compute time-of-day encoding features.

        Args:
            df: DataFrame with datetime index

        Returns:
            DataFrame with columns: tod_sin, tod_cos, is_open_window,
                                   is_close_window, is_midday
        """
        # Get minutes from market open
        tod = self._compute_minutes_from_open(df.index)

        # Normalize to [0, 1]
        tod_norm = tod / self.trading_minutes

        result = pd.DataFrame(index=df.index)

        # Cyclical encoding
        result["tod_sin"] = np.sin(2 * np.pi * tod_norm)
        result["tod_cos"] = np.cos(2 * np.pi * tod_norm)

        # Session window flags
        result["is_open_window"] = (tod < self.open_window_minutes).astype(int)
        close_threshold = self.trading_minutes - self.close_window_minutes
        result["is_close_window"] = (tod > close_threshold).astype(int)
        result["is_midday"] = (
            (tod >= self.midday_start_minutes) & (tod <= self.midday_end_minutes)
        ).astype(int)

        return result
