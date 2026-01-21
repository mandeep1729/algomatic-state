"""Feature normalization for state representation."""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

import numpy as np


class NormalizationMethod(Enum):
    """Available normalization methods."""

    ZSCORE = "zscore"
    ROBUST = "robust"


@dataclass
class NormalizerConfig:
    """Configuration for feature normalizer.

    Attributes:
        method: Normalization method (zscore or robust)
        clip_value: Value to clip extreme values (in std units)
        rolling_window: Optional rolling window for online normalization
    """

    method: NormalizationMethod = NormalizationMethod.ZSCORE
    clip_value: float = 3.0
    rolling_window: int | None = None


class FeatureNormalizer:
    """Normalize features for state representation learning.

    Supports:
    - Z-score normalization: (x - mean) / std
    - Robust scaling: (x - median) / IQR
    - Rolling normalization with configurable lookback
    - Clipping extreme values

    Example:
        >>> normalizer = FeatureNormalizer(method="zscore", clip_value=3.0)
        >>> normalizer.fit(train_windows)
        >>> normalized = normalizer.transform(test_windows)
    """

    def __init__(
        self,
        method: Literal["zscore", "robust"] = "zscore",
        clip_value: float = 3.0,
        rolling_window: int | None = None,
    ):
        """Initialize FeatureNormalizer.

        Args:
            method: Normalization method ("zscore" or "robust")
            clip_value: Clip values beyond this many std/IQR (default 3.0)
            rolling_window: Optional rolling window size for online normalization
        """
        self.method = NormalizationMethod(method)
        self.clip_value = clip_value
        self.rolling_window = rolling_window

        # Fitted parameters
        self._mean: np.ndarray | None = None
        self._std: np.ndarray | None = None
        self._median: np.ndarray | None = None
        self._iqr: np.ndarray | None = None
        self._is_fitted = False

    @property
    def config(self) -> NormalizerConfig:
        """Return current configuration."""
        return NormalizerConfig(
            method=self.method,
            clip_value=self.clip_value,
            rolling_window=self.rolling_window,
        )

    @property
    def is_fitted(self) -> bool:
        """Check if normalizer has been fitted."""
        return self._is_fitted

    def fit(self, windows: np.ndarray) -> "FeatureNormalizer":
        """Fit normalizer on training data.

        Args:
            windows: Array of shape (n_samples, window_size, n_features)
                     or (n_samples, n_features)

        Returns:
            self (for method chaining)
        """
        # Flatten to 2D if 3D
        if windows.ndim == 3:
            flat = windows.reshape(-1, windows.shape[-1])
        else:
            flat = windows

        if self.method == NormalizationMethod.ZSCORE:
            self._mean = np.mean(flat, axis=0)
            self._std = np.std(flat, axis=0)
            # Avoid division by zero
            self._std = np.where(self._std < 1e-8, 1.0, self._std)
        else:  # ROBUST
            self._median = np.median(flat, axis=0)
            q75 = np.percentile(flat, 75, axis=0)
            q25 = np.percentile(flat, 25, axis=0)
            self._iqr = q75 - q25
            # Avoid division by zero
            self._iqr = np.where(self._iqr < 1e-8, 1.0, self._iqr)

        self._is_fitted = True
        return self

    def transform(self, windows: np.ndarray) -> np.ndarray:
        """Transform data using fitted parameters.

        Args:
            windows: Array of shape (n_samples, window_size, n_features)
                     or (n_samples, n_features)

        Returns:
            Normalized array of same shape
        """
        if not self._is_fitted:
            raise RuntimeError("Normalizer must be fitted before transform")

        original_shape = windows.shape
        is_3d = windows.ndim == 3

        # Flatten to 2D for normalization
        if is_3d:
            flat = windows.reshape(-1, windows.shape[-1])
        else:
            flat = windows

        # Normalize
        if self.method == NormalizationMethod.ZSCORE:
            normalized = (flat - self._mean) / self._std
        else:  # ROBUST
            normalized = (flat - self._median) / self._iqr

        # Clip extreme values
        if self.clip_value is not None:
            normalized = np.clip(normalized, -self.clip_value, self.clip_value)

        # Reshape back to original shape
        if is_3d:
            normalized = normalized.reshape(original_shape)

        return normalized.astype(np.float32)

    def fit_transform(self, windows: np.ndarray) -> np.ndarray:
        """Fit and transform in one step.

        Args:
            windows: Array of shape (n_samples, window_size, n_features)

        Returns:
            Normalized array
        """
        return self.fit(windows).transform(windows)

    def inverse_transform(self, normalized: np.ndarray) -> np.ndarray:
        """Inverse transform normalized data back to original scale.

        Args:
            normalized: Normalized array

        Returns:
            Denormalized array
        """
        if not self._is_fitted:
            raise RuntimeError("Normalizer must be fitted before inverse_transform")

        original_shape = normalized.shape
        is_3d = normalized.ndim == 3

        if is_3d:
            flat = normalized.reshape(-1, normalized.shape[-1])
        else:
            flat = normalized

        if self.method == NormalizationMethod.ZSCORE:
            denormalized = flat * self._std + self._mean
        else:  # ROBUST
            denormalized = flat * self._iqr + self._median

        if is_3d:
            denormalized = denormalized.reshape(original_shape)

        return denormalized

    def get_params(self) -> dict:
        """Get fitted parameters.

        Returns:
            Dictionary of fitted parameters
        """
        if not self._is_fitted:
            return {}

        if self.method == NormalizationMethod.ZSCORE:
            return {"mean": self._mean.copy(), "std": self._std.copy()}
        else:
            return {"median": self._median.copy(), "iqr": self._iqr.copy()}

    def set_params(self, params: dict) -> None:
        """Set parameters from saved values.

        Args:
            params: Dictionary of parameters (from get_params)
        """
        if "mean" in params:
            self._mean = params["mean"]
            self._std = params["std"]
            self.method = NormalizationMethod.ZSCORE
        else:
            self._median = params["median"]
            self._iqr = params["iqr"]
            self.method = NormalizationMethod.ROBUST
        self._is_fitted = True
