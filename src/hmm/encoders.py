"""Encoders for state vector learning.

Implements:
- BaseEncoder: Abstract interface
- PCAEncoder: PCA-based dimensionality reduction
- TemporalPCAEncoder: PCA with temporal window input
"""

import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from sklearn.decomposition import PCA


@dataclass
class EncoderMetrics:
    """Metrics from encoder training.

    Attributes:
        explained_variance_ratio: Variance explained by each component
        total_variance_explained: Total variance explained
        reconstruction_error: Mean squared reconstruction error
        n_components_for_95: Components needed for 95% variance
    """

    explained_variance_ratio: np.ndarray
    total_variance_explained: float
    reconstruction_error: float
    n_components_for_95: int


class BaseEncoder(ABC):
    """Abstract base class for state vector encoders."""

    @abstractmethod
    def fit(self, X: np.ndarray) -> "BaseEncoder":
        """Fit encoder to training data.

        Args:
            X: Training data of shape (n_samples, n_features) or
               (n_samples, window_size, n_features) for temporal encoders

        Returns:
            Self
        """
        pass

    @abstractmethod
    def transform(self, X: np.ndarray) -> np.ndarray:
        """Encode data to latent space.

        Args:
            X: Data to encode

        Returns:
            Latent vectors of shape (n_samples, latent_dim)
        """
        pass

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit and transform in one step.

        Args:
            X: Training data

        Returns:
            Latent vectors
        """
        return self.fit(X).transform(X)

    @abstractmethod
    def inverse_transform(self, Z: np.ndarray) -> np.ndarray:
        """Decode latent vectors back to feature space.

        Args:
            Z: Latent vectors of shape (n_samples, latent_dim)

        Returns:
            Reconstructed features
        """
        pass

    @property
    @abstractmethod
    def latent_dim(self) -> int:
        """Return dimensionality of latent space."""
        pass

    @property
    @abstractmethod
    def input_dim(self) -> int:
        """Return dimensionality of input space."""
        pass

    def reconstruction_error(self, X: np.ndarray) -> np.ndarray:
        """Compute per-sample reconstruction error.

        Args:
            X: Input data

        Returns:
            Array of reconstruction errors (MSE per sample)
        """
        Z = self.transform(X)
        X_recon = self.inverse_transform(Z)
        return np.mean((X - X_recon) ** 2, axis=-1)

    def save(self, path: Path | str) -> None:
        """Save encoder to pickle file.

        Args:
            path: Output file path
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: Path | str) -> "BaseEncoder":
        """Load encoder from pickle file.

        Args:
            path: Input file path

        Returns:
            Loaded encoder instance
        """
        with open(path, "rb") as f:
            return pickle.load(f)


class PCAEncoder(BaseEncoder):
    """PCA-based encoder for dimensionality reduction.

    Transforms: z_t = W^T @ x̃_t

    This is the recommended baseline encoder. PCA is:
    - Fast to train
    - Stable across retrains
    - Interpretable (via loadings)
    """

    def __init__(
        self,
        latent_dim: int = 8,
        whiten: bool = False,
    ):
        """Initialize PCA encoder.

        Args:
            latent_dim: Number of principal components (latent dimension)
            whiten: Whether to whiten the output (decorrelate and unit variance)
        """
        self._latent_dim = latent_dim
        self.whiten = whiten
        self.pca_: Optional[PCA] = None
        self._input_dim: Optional[int] = None
        self.metrics_: Optional[EncoderMetrics] = None

    @property
    def latent_dim(self) -> int:
        """Return latent dimensionality."""
        return self._latent_dim

    @property
    def input_dim(self) -> int:
        """Return input dimensionality."""
        if self._input_dim is None:
            raise ValueError("Encoder not fitted")
        return self._input_dim

    def fit(self, X: np.ndarray) -> "PCAEncoder":
        """Fit PCA to training data.

        Args:
            X: Training data of shape (n_samples, n_features)

        Returns:
            Self
        """
        X = np.asarray(X)
        if X.ndim != 2:
            raise ValueError(f"Expected 2D input, got shape {X.shape}")

        self._input_dim = X.shape[1]

        mask = ~np.any(np.isnan(X), axis=1)
        X_clean = X[mask]

        if len(X_clean) < self._latent_dim:
            raise ValueError(
                f"Need at least {self._latent_dim} valid samples, got {len(X_clean)}"
            )

        n_components = min(self._latent_dim, X_clean.shape[0], X_clean.shape[1])

        self.pca_ = PCA(n_components=n_components, whiten=self.whiten)
        self.pca_.fit(X_clean)

        self._latent_dim = n_components

        self._compute_metrics(X_clean)

        return self

    def _compute_metrics(self, X: np.ndarray) -> None:
        """Compute training metrics."""
        Z = self.pca_.transform(X)
        X_recon = self.pca_.inverse_transform(Z)
        recon_error = np.mean((X - X_recon) ** 2)

        cumsum = np.cumsum(self.pca_.explained_variance_ratio_)
        n_for_95 = np.searchsorted(cumsum, 0.95) + 1

        self.metrics_ = EncoderMetrics(
            explained_variance_ratio=self.pca_.explained_variance_ratio_,
            total_variance_explained=cumsum[-1] if len(cumsum) > 0 else 0.0,
            reconstruction_error=recon_error,
            n_components_for_95=min(n_for_95, len(cumsum)),
        )

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Encode data to latent space.

        Args:
            X: Data of shape (n_samples, n_features)

        Returns:
            Latent vectors of shape (n_samples, latent_dim)
        """
        if self.pca_ is None:
            raise ValueError("Encoder not fitted. Call fit() first.")

        X = np.asarray(X)
        if X.ndim == 1:
            X = X.reshape(1, -1)

        result = np.full((X.shape[0], self._latent_dim), np.nan)

        mask = ~np.any(np.isnan(X), axis=1)
        if mask.sum() > 0:
            result[mask] = self.pca_.transform(X[mask])

        return result

    def inverse_transform(self, Z: np.ndarray) -> np.ndarray:
        """Decode latent vectors back to feature space.

        Args:
            Z: Latent vectors of shape (n_samples, latent_dim)

        Returns:
            Reconstructed features of shape (n_samples, n_features)
        """
        if self.pca_ is None:
            raise ValueError("Encoder not fitted. Call fit() first.")

        Z = np.asarray(Z)
        if Z.ndim == 1:
            Z = Z.reshape(1, -1)

        return self.pca_.inverse_transform(Z)

    @property
    def components(self) -> np.ndarray:
        """Return PCA components (loadings).

        Returns:
            Components of shape (latent_dim, n_features)
        """
        if self.pca_ is None:
            raise ValueError("Encoder not fitted")
        return self.pca_.components_

    @property
    def explained_variance_ratio(self) -> np.ndarray:
        """Return explained variance ratio per component."""
        if self.pca_ is None:
            raise ValueError("Encoder not fitted")
        return self.pca_.explained_variance_ratio_


class TemporalPCAEncoder(BaseEncoder):
    """PCA encoder with temporal window input.

    Flattens a window of features before applying PCA.
    Input: X_t = [x_{t-L+1}, ..., x_t] of shape (L, D)
    Flattened: [x_{t-L+1}^1, ..., x_{t-L+1}^D, ..., x_t^1, ..., x_t^D]
    Output: z_t of shape (d,)
    """

    def __init__(
        self,
        latent_dim: int = 8,
        window_size: int = 5,
        whiten: bool = False,
    ):
        """Initialize temporal PCA encoder.

        Args:
            latent_dim: Latent dimensionality
            window_size: Number of time steps in window
            whiten: Whether to whiten output
        """
        self._latent_dim = latent_dim
        self.window_size = window_size
        self.whiten = whiten
        self.pca_encoder_: Optional[PCAEncoder] = None
        self._feature_dim: Optional[int] = None

    @property
    def latent_dim(self) -> int:
        """Return latent dimensionality."""
        return self._latent_dim

    @property
    def input_dim(self) -> int:
        """Return flattened input dimensionality."""
        if self._feature_dim is None:
            raise ValueError("Encoder not fitted")
        return self.window_size * self._feature_dim

    @property
    def feature_dim(self) -> int:
        """Return per-timestep feature dimensionality."""
        if self._feature_dim is None:
            raise ValueError("Encoder not fitted")
        return self._feature_dim

    def fit(self, X: np.ndarray) -> "TemporalPCAEncoder":
        """Fit encoder to windowed training data.

        Args:
            X: Training data of shape (n_samples, window_size, n_features)

        Returns:
            Self
        """
        X = np.asarray(X)
        if X.ndim != 3:
            raise ValueError(f"Expected 3D input (n, window, features), got {X.shape}")

        if X.shape[1] != self.window_size:
            raise ValueError(
                f"Window size mismatch: expected {self.window_size}, got {X.shape[1]}"
            )

        self._feature_dim = X.shape[2]

        X_flat = X.reshape(X.shape[0], -1)

        self.pca_encoder_ = PCAEncoder(
            latent_dim=self._latent_dim,
            whiten=self.whiten,
        )
        self.pca_encoder_.fit(X_flat)

        self._latent_dim = self.pca_encoder_.latent_dim

        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Encode windowed data to latent space.

        Args:
            X: Data of shape (n_samples, window_size, n_features)

        Returns:
            Latent vectors of shape (n_samples, latent_dim)
        """
        if self.pca_encoder_ is None:
            raise ValueError("Encoder not fitted. Call fit() first.")

        X = np.asarray(X)
        if X.ndim == 2:
            X = X.reshape(1, X.shape[0], X.shape[1])

        X_flat = X.reshape(X.shape[0], -1)
        return self.pca_encoder_.transform(X_flat)

    def inverse_transform(self, Z: np.ndarray) -> np.ndarray:
        """Decode latent vectors back to windowed feature space.

        Args:
            Z: Latent vectors of shape (n_samples, latent_dim)

        Returns:
            Reconstructed windows of shape (n_samples, window_size, n_features)
        """
        if self.pca_encoder_ is None:
            raise ValueError("Encoder not fitted. Call fit() first.")

        X_flat = self.pca_encoder_.inverse_transform(Z)
        return X_flat.reshape(-1, self.window_size, self._feature_dim)

    @property
    def metrics(self) -> Optional[EncoderMetrics]:
        """Return training metrics."""
        if self.pca_encoder_ is None:
            return None
        return self.pca_encoder_.metrics_


def create_windows(
    X: np.ndarray,
    window_size: int,
    stride: int = 1,
) -> np.ndarray:
    """Create sliding windows from time series data.

    Args:
        X: Data of shape (n_timesteps, n_features)
        window_size: Size of sliding window
        stride: Step between windows

    Returns:
        Windowed data of shape (n_windows, window_size, n_features)
    """
    X = np.asarray(X)
    if X.ndim != 2:
        raise ValueError(f"Expected 2D input, got shape {X.shape}")

    n_timesteps, n_features = X.shape

    if window_size > n_timesteps:
        raise ValueError(
            f"Window size {window_size} > n_timesteps {n_timesteps}"
        )

    n_windows = (n_timesteps - window_size) // stride + 1

    windows = np.zeros((n_windows, window_size, n_features))

    for i in range(n_windows):
        start = i * stride
        windows[i] = X[start : start + window_size]

    return windows


def select_latent_dim(
    X: np.ndarray,
    variance_threshold: float = 0.95,
    max_dim: int = 16,
    min_dim: int = 2,
) -> int:
    """Select latent dimension based on explained variance.

    Args:
        X: Training data of shape (n_samples, n_features)
        variance_threshold: Target cumulative explained variance
        max_dim: Maximum latent dimension
        min_dim: Minimum latent dimension

    Returns:
        Recommended latent dimension
    """
    X = np.asarray(X)
    mask = ~np.any(np.isnan(X), axis=1)
    X_clean = X[mask]

    max_possible = min(X_clean.shape[0], X_clean.shape[1], max_dim)

    pca = PCA(n_components=max_possible)
    pca.fit(X_clean)

    cumsum = np.cumsum(pca.explained_variance_ratio_)
    n_for_threshold = np.searchsorted(cumsum, variance_threshold) + 1

    return max(min_dim, min(n_for_threshold, max_dim))


def create_encoder(
    encoder_type: Literal["pca", "temporal_pca"],
    latent_dim: int = 8,
    window_size: int = 1,
    whiten: bool = False,
) -> BaseEncoder:
    """Factory function to create an encoder.

    Args:
        encoder_type: Type of encoder
        latent_dim: Latent dimensionality
        window_size: Window size for temporal encoder
        whiten: Whether to whiten output

    Returns:
        Encoder instance
    """
    if encoder_type == "pca":
        return PCAEncoder(latent_dim=latent_dim, whiten=whiten)
    elif encoder_type == "temporal_pca":
        return TemporalPCAEncoder(
            latent_dim=latent_dim,
            window_size=window_size,
            whiten=whiten,
        )
    else:
        raise ValueError(f"Unknown encoder type: {encoder_type}")
