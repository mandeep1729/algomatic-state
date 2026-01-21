"""Temporal window generation for state representation."""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class WindowConfig:
    """Configuration for window generation.

    Attributes:
        window_size: Number of time steps in each window (default 60)
        stride: Step size between windows (default 1)
    """

    window_size: int = 60
    stride: int = 1


class WindowGenerator:
    """Generate sliding windows of features for state representation.

    Creates temporal windows from feature DataFrames for use in state
    learning models (PCA, autoencoders, etc.).

    Example:
        >>> generator = WindowGenerator(window_size=60, stride=1)
        >>> windows, timestamps = generator.generate(features_df)
        >>> print(windows.shape)  # (n_samples, 60, n_features)
    """

    def __init__(self, window_size: int = 60, stride: int = 1):
        """Initialize WindowGenerator.

        Args:
            window_size: Number of time steps in each window
            stride: Step size between consecutive windows
        """
        self.window_size = window_size
        self.stride = stride

    @property
    def config(self) -> WindowConfig:
        """Return current configuration."""
        return WindowConfig(window_size=self.window_size, stride=self.stride)

    def generate(
        self, df: pd.DataFrame, return_timestamps: bool = True
    ) -> tuple[np.ndarray, pd.DatetimeIndex | None]:
        """Generate sliding windows from feature DataFrame.

        Args:
            df: DataFrame with datetime index and feature columns
            return_timestamps: Whether to return aligned timestamps

        Returns:
            Tuple of:
                - windows: np.ndarray of shape (n_samples, window_size, n_features)
                - timestamps: DatetimeIndex of window end times (if return_timestamps=True)
        """
        if len(df) < self.window_size:
            raise ValueError(
                f"DataFrame has {len(df)} rows, but window_size is {self.window_size}"
            )

        n_features = len(df.columns)
        values = df.values

        # Calculate number of windows
        n_windows = (len(df) - self.window_size) // self.stride + 1

        # Pre-allocate output array
        windows = np.zeros((n_windows, self.window_size, n_features), dtype=np.float32)

        # Extract timestamps for window end times
        timestamps = []

        for i in range(n_windows):
            start_idx = i * self.stride
            end_idx = start_idx + self.window_size
            windows[i] = values[start_idx:end_idx]
            timestamps.append(df.index[end_idx - 1])

        if return_timestamps:
            return windows, pd.DatetimeIndex(timestamps)
        return windows, None

    def generate_single(self, df: pd.DataFrame) -> np.ndarray:
        """Generate a single window from the most recent data.

        Useful for live/streaming applications.

        Args:
            df: DataFrame with at least window_size rows

        Returns:
            Single window of shape (window_size, n_features)
        """
        if len(df) < self.window_size:
            raise ValueError(
                f"DataFrame has {len(df)} rows, but window_size is {self.window_size}"
            )

        return df.iloc[-self.window_size :].values.astype(np.float32)

    def flatten_windows(self, windows: np.ndarray) -> np.ndarray:
        """Flatten windows for use with PCA or other flat models.

        Args:
            windows: Array of shape (n_samples, window_size, n_features)

        Returns:
            Flattened array of shape (n_samples, window_size * n_features)
        """
        n_samples = windows.shape[0]
        return windows.reshape(n_samples, -1)

    def unflatten_windows(
        self, flat_windows: np.ndarray, n_features: int
    ) -> np.ndarray:
        """Unflatten windows back to 3D shape.

        Args:
            flat_windows: Array of shape (n_samples, window_size * n_features)
            n_features: Number of features per time step

        Returns:
            Array of shape (n_samples, window_size, n_features)
        """
        n_samples = flat_windows.shape[0]
        return flat_windows.reshape(n_samples, self.window_size, n_features)
