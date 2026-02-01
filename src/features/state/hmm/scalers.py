"""Scalers for feature normalization.

Implements:
- RobustScaler: median/IQR scaling for heavy tails
- StandardScaler: mean/std scaling
- YeoJohnsonScaler: power transform for Gaussian alignment
- Combined scaler with stationarity transforms
"""

import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import numpy as np
import pandas as pd
from scipy import stats


EPS = 1e-9


class BaseScaler(ABC):
    """Abstract base class for feature scalers."""

    @abstractmethod
    def fit(self, X: np.ndarray) -> "BaseScaler":
        """Fit scaler to training data.

        Args:
            X: Training data of shape (n_samples, n_features)

        Returns:
            Self
        """
        pass

    @abstractmethod
    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform data using fitted parameters.

        Args:
            X: Data of shape (n_samples, n_features)

        Returns:
            Transformed data of same shape
        """
        pass

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit and transform in one step.

        Args:
            X: Training data of shape (n_samples, n_features)

        Returns:
            Transformed data
        """
        return self.fit(X).transform(X)

    @abstractmethod
    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        """Inverse transform data.

        Args:
            X: Transformed data

        Returns:
            Original scale data
        """
        pass

    def save(self, path: Path | str) -> None:
        """Save scaler to pickle file.

        Args:
            path: Output file path
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: Path | str) -> "BaseScaler":
        """Load scaler from pickle file.

        Args:
            path: Input file path

        Returns:
            Loaded scaler instance
        """
        with open(path, "rb") as f:
            return pickle.load(f)


class RobustScaler(BaseScaler):
    """Robust scaler using median and IQR.

    More robust to outliers than StandardScaler.
    Transforms: (x - median) / IQR
    """

    def __init__(
        self,
        quantile_range: tuple[float, float] = (25.0, 75.0),
        clip_std: Optional[float] = 5.0,
    ):
        """Initialize robust scaler.

        Args:
            quantile_range: Percentiles for IQR computation
            clip_std: Clip outliers beyond N std devs (None to disable)
        """
        self.quantile_range = quantile_range
        self.clip_std = clip_std
        self.center_: Optional[np.ndarray] = None
        self.scale_: Optional[np.ndarray] = None
        self.n_features_: Optional[int] = None

    def fit(self, X: np.ndarray) -> "RobustScaler":
        """Fit scaler to training data.

        Args:
            X: Training data of shape (n_samples, n_features)

        Returns:
            Self
        """
        X = np.asarray(X)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        self.n_features_ = X.shape[1]

        self.center_ = np.nanmedian(X, axis=0)

        q_low, q_high = self.quantile_range
        percentiles = np.nanpercentile(X, [q_low, q_high], axis=0)
        self.scale_ = percentiles[1] - percentiles[0]
        self.scale_ = np.where(self.scale_ < EPS, 1.0, self.scale_)

        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform data using fitted parameters.

        Args:
            X: Data of shape (n_samples, n_features)

        Returns:
            Transformed data
        """
        if self.center_ is None:
            raise ValueError("Scaler not fitted. Call fit() first.")

        X = np.asarray(X)
        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(-1, 1)

        X_scaled = (X - self.center_) / self.scale_

        if self.clip_std is not None:
            X_scaled = np.clip(X_scaled, -self.clip_std, self.clip_std)

        if squeeze:
            X_scaled = X_scaled.ravel()

        return X_scaled

    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        """Inverse transform data.

        Args:
            X: Transformed data

        Returns:
            Original scale data
        """
        if self.center_ is None:
            raise ValueError("Scaler not fitted. Call fit() first.")

        X = np.asarray(X)
        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(-1, 1)

        X_orig = X * self.scale_ + self.center_

        if squeeze:
            X_orig = X_orig.ravel()

        return X_orig


class StandardScaler(BaseScaler):
    """Standard scaler using mean and standard deviation.

    Transforms: (x - mean) / std
    """

    def __init__(self, clip_std: Optional[float] = 5.0):
        """Initialize standard scaler.

        Args:
            clip_std: Clip outliers beyond N std devs (None to disable)
        """
        self.clip_std = clip_std
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None
        self.n_features_: Optional[int] = None

    def fit(self, X: np.ndarray) -> "StandardScaler":
        """Fit scaler to training data.

        Args:
            X: Training data of shape (n_samples, n_features)

        Returns:
            Self
        """
        X = np.asarray(X)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        self.n_features_ = X.shape[1]
        self.mean_ = np.nanmean(X, axis=0)
        self.std_ = np.nanstd(X, axis=0)
        self.std_ = np.where(self.std_ < EPS, 1.0, self.std_)

        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform data using fitted parameters.

        Args:
            X: Data of shape (n_samples, n_features)

        Returns:
            Transformed data
        """
        if self.mean_ is None:
            raise ValueError("Scaler not fitted. Call fit() first.")

        X = np.asarray(X)
        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(-1, 1)

        X_scaled = (X - self.mean_) / self.std_

        if self.clip_std is not None:
            X_scaled = np.clip(X_scaled, -self.clip_std, self.clip_std)

        if squeeze:
            X_scaled = X_scaled.ravel()

        return X_scaled

    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        """Inverse transform data.

        Args:
            X: Transformed data

        Returns:
            Original scale data
        """
        if self.mean_ is None:
            raise ValueError("Scaler not fitted. Call fit() first.")

        X = np.asarray(X)
        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(-1, 1)

        X_orig = X * self.std_ + self.mean_

        if squeeze:
            X_orig = X_orig.ravel()

        return X_orig


class YeoJohnsonScaler(BaseScaler):
    """Yeo-Johnson power transform for Gaussian alignment.

    Applies Yeo-Johnson transform followed by standard scaling.
    Good for features with non-Gaussian distributions.
    """

    def __init__(self, clip_std: Optional[float] = 5.0):
        """Initialize Yeo-Johnson scaler.

        Args:
            clip_std: Clip outliers beyond N std devs after transform
        """
        self.clip_std = clip_std
        self.lambdas_: Optional[np.ndarray] = None
        self.mean_: Optional[np.ndarray] = None
        self.std_: Optional[np.ndarray] = None
        self.n_features_: Optional[int] = None

    def fit(self, X: np.ndarray) -> "YeoJohnsonScaler":
        """Fit scaler to training data.

        Args:
            X: Training data of shape (n_samples, n_features)

        Returns:
            Self
        """
        X = np.asarray(X)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        self.n_features_ = X.shape[1]
        self.lambdas_ = np.zeros(self.n_features_)

        X_transformed = np.zeros_like(X)

        for j in range(self.n_features_):
            col = X[:, j]
            mask = ~np.isnan(col)
            if mask.sum() > 10:
                X_transformed[mask, j], self.lambdas_[j] = stats.yeojohnson(col[mask])
            else:
                X_transformed[:, j] = col
                self.lambdas_[j] = 1.0

        self.mean_ = np.nanmean(X_transformed, axis=0)
        self.std_ = np.nanstd(X_transformed, axis=0)
        self.std_ = np.where(self.std_ < EPS, 1.0, self.std_)

        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform data using fitted parameters.

        Args:
            X: Data of shape (n_samples, n_features)

        Returns:
            Transformed data
        """
        if self.lambdas_ is None:
            raise ValueError("Scaler not fitted. Call fit() first.")

        X = np.asarray(X)
        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(-1, 1)

        X_transformed = np.zeros_like(X, dtype=float)

        for j in range(X.shape[1]):
            col = X[:, j]
            mask = ~np.isnan(col)
            if mask.sum() > 0:
                X_transformed[mask, j] = stats.yeojohnson(
                    col[mask], lmbda=self.lambdas_[j]
                )
            X_transformed[~mask, j] = np.nan

        X_scaled = (X_transformed - self.mean_) / self.std_

        if self.clip_std is not None:
            X_scaled = np.clip(X_scaled, -self.clip_std, self.clip_std)

        if squeeze:
            X_scaled = X_scaled.ravel()

        return X_scaled

    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        """Inverse transform data.

        Note: Yeo-Johnson inverse is not always well-defined for all values.

        Args:
            X: Transformed data

        Returns:
            Approximately original scale data
        """
        if self.mean_ is None:
            raise ValueError("Scaler not fitted. Call fit() first.")

        X = np.asarray(X)
        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(-1, 1)

        X_unscaled = X * self.std_ + self.mean_

        X_orig = np.zeros_like(X_unscaled)
        for j in range(X.shape[1]):
            col = X_unscaled[:, j]
            X_orig[:, j] = self._yeojohnson_inverse(col, self.lambdas_[j])

        if squeeze:
            X_orig = X_orig.ravel()

        return X_orig

    @staticmethod
    def _yeojohnson_inverse(y: np.ndarray, lmbda: float) -> np.ndarray:
        """Inverse Yeo-Johnson transform."""
        x = np.zeros_like(y)

        pos = y >= 0
        neg = ~pos

        if lmbda == 0:
            x[pos] = np.exp(y[pos]) - 1
        else:
            x[pos] = np.power(y[pos] * lmbda + 1, 1 / lmbda) - 1

        if lmbda == 2:
            x[neg] = 1 - np.exp(-y[neg])
        else:
            x[neg] = 1 - np.power(-(2 - lmbda) * y[neg] + 1, 1 / (2 - lmbda))

        return x


@dataclass
class FeatureScalerConfig:
    """Configuration for per-feature scaling."""

    scaler_type: Literal["robust", "standard", "yeo_johnson", "none"]
    clip_std: Optional[float] = 5.0
    differencing: bool = False


class CombinedScaler(BaseScaler):
    """Combined scaler with per-feature configuration.

    Supports:
    - Different scaler types per feature
    - Optional differencing for stationarity
    - Missing value handling
    """

    def __init__(
        self,
        feature_names: list[str],
        configs: Optional[dict[str, FeatureScalerConfig]] = None,
        default_scaler: Literal["robust", "standard", "yeo_johnson"] = "robust",
        default_clip_std: float = 5.0,
    ):
        """Initialize combined scaler.

        Args:
            feature_names: Ordered list of feature names
            configs: Per-feature configurations
            default_scaler: Default scaler type
            default_clip_std: Default clip threshold
        """
        self.feature_names = feature_names
        self.configs = configs or {}
        self.default_scaler = default_scaler
        self.default_clip_std = default_clip_std

        self.scalers_: dict[str, BaseScaler] = {}
        self.diff_first_vals_: dict[str, float] = {}
        self.fitted_ = False

    def _get_config(self, name: str) -> FeatureScalerConfig:
        """Get configuration for a feature."""
        if name in self.configs:
            return self.configs[name]
        return FeatureScalerConfig(
            scaler_type=self.default_scaler,
            clip_std=self.default_clip_std,
            differencing=False,
        )

    def _create_scaler(self, config: FeatureScalerConfig) -> Optional[BaseScaler]:
        """Create scaler instance from config."""
        if config.scaler_type == "robust":
            return RobustScaler(clip_std=config.clip_std)
        elif config.scaler_type == "standard":
            return StandardScaler(clip_std=config.clip_std)
        elif config.scaler_type == "yeo_johnson":
            return YeoJohnsonScaler(clip_std=config.clip_std)
        elif config.scaler_type == "none":
            return None
        else:
            raise ValueError(f"Unknown scaler type: {config.scaler_type}")

    def fit(self, X: np.ndarray) -> "CombinedScaler":
        """Fit scaler to training data.

        Args:
            X: Training data of shape (n_samples, n_features)

        Returns:
            Self
        """
        X = np.asarray(X)
        if X.ndim == 1:
            X = X.reshape(-1, 1)

        if X.shape[1] != len(self.feature_names):
            raise ValueError(
                f"Expected {len(self.feature_names)} features, got {X.shape[1]}"
            )

        for j, name in enumerate(self.feature_names):
            config = self._get_config(name)
            col = X[:, j].copy()

            if config.differencing:
                mask = ~np.isnan(col)
                first_valid = np.where(mask)[0]
                if len(first_valid) > 0:
                    self.diff_first_vals_[name] = col[first_valid[0]]
                    col[mask] = np.diff(col[mask], prepend=col[first_valid[0]])

            scaler = self._create_scaler(config)
            if scaler is not None:
                mask = ~np.isnan(col)
                if mask.sum() > 0:
                    scaler.fit(col[mask].reshape(-1, 1))
            self.scalers_[name] = scaler

        self.fitted_ = True
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Transform data using fitted parameters.

        Args:
            X: Data of shape (n_samples, n_features)

        Returns:
            Transformed data
        """
        if not self.fitted_:
            raise ValueError("Scaler not fitted. Call fit() first.")

        X = np.asarray(X)
        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(-1, 1)

        X_out = np.zeros_like(X, dtype=float)

        for j, name in enumerate(self.feature_names):
            config = self._get_config(name)
            col = X[:, j].copy()

            if config.differencing:
                mask = ~np.isnan(col)
                if mask.sum() > 1:
                    first_val = self.diff_first_vals_.get(name, col[mask][0])
                    col[mask] = np.diff(col[mask], prepend=first_val)

            scaler = self.scalers_.get(name)
            if scaler is not None:
                mask = ~np.isnan(col)
                if mask.sum() > 0:
                    col[mask] = scaler.transform(col[mask].reshape(-1, 1)).ravel()

            X_out[:, j] = col

        if squeeze:
            X_out = X_out.ravel()

        return X_out

    def inverse_transform(self, X: np.ndarray) -> np.ndarray:
        """Inverse transform data.

        Note: Differencing inverse requires cumulative sum which may accumulate errors.

        Args:
            X: Transformed data

        Returns:
            Approximately original scale data
        """
        if not self.fitted_:
            raise ValueError("Scaler not fitted. Call fit() first.")

        X = np.asarray(X)
        squeeze = X.ndim == 1
        if squeeze:
            X = X.reshape(-1, 1)

        X_out = np.zeros_like(X, dtype=float)

        for j, name in enumerate(self.feature_names):
            config = self._get_config(name)
            col = X[:, j].copy()

            scaler = self.scalers_.get(name)
            if scaler is not None:
                mask = ~np.isnan(col)
                if mask.sum() > 0:
                    col[mask] = scaler.inverse_transform(col[mask].reshape(-1, 1)).ravel()

            if config.differencing:
                mask = ~np.isnan(col)
                if mask.sum() > 0:
                    first_val = self.diff_first_vals_.get(name, 0.0)
                    col[mask] = np.cumsum(col[mask]) + first_val

            X_out[:, j] = col

        if squeeze:
            X_out = X_out.ravel()

        return X_out


def create_scaler(
    scaler_type: Literal["robust", "standard", "yeo_johnson"],
    clip_std: Optional[float] = 5.0,
) -> BaseScaler:
    """Factory function to create a scaler.

    Args:
        scaler_type: Type of scaler
        clip_std: Outlier clipping threshold

    Returns:
        Scaler instance
    """
    if scaler_type == "robust":
        return RobustScaler(clip_std=clip_std)
    elif scaler_type == "standard":
        return StandardScaler(clip_std=clip_std)
    elif scaler_type == "yeo_johnson":
        return YeoJohnsonScaler(clip_std=clip_std)
    else:
        raise ValueError(f"Unknown scaler type: {scaler_type}")
