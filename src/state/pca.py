"""PCA-based state extraction (baseline)."""

from dataclasses import dataclass

import numpy as np
from sklearn.decomposition import PCA


@dataclass
class PCAConfig:
    """Configuration for PCA state extractor.

    Attributes:
        n_components: Number of components (or variance ratio if < 1)
        whiten: Whether to whiten the output
    """

    n_components: int | float = 8
    whiten: bool = False


class PCAStateExtractor:
    """Extract state representations using PCA.

    A baseline approach for state representation that:
    - Flattens temporal windows
    - Fits PCA on training data
    - Extracts top k components or components explaining % variance

    Example:
        >>> extractor = PCAStateExtractor(n_components=8)
        >>> extractor.fit(train_windows)
        >>> states = extractor.transform(test_windows)
        >>> print(states.shape)  # (n_samples, 8)
    """

    def __init__(
        self,
        n_components: int | float = 8,
        whiten: bool = False,
    ):
        """Initialize PCAStateExtractor.

        Args:
            n_components: Number of components to keep.
                          If int, keep that many components.
                          If float < 1, keep components explaining that variance ratio.
            whiten: Whether to whiten the output (decorrelate and unit variance)
        """
        self.n_components = n_components
        self.whiten = whiten
        self._pca: PCA | None = None
        self._is_fitted = False

    @property
    def config(self) -> PCAConfig:
        """Return current configuration."""
        return PCAConfig(n_components=self.n_components, whiten=self.whiten)

    @property
    def is_fitted(self) -> bool:
        """Check if extractor has been fitted."""
        return self._is_fitted

    @property
    def explained_variance_ratio(self) -> np.ndarray | None:
        """Return explained variance ratio per component."""
        if self._pca is None:
            return None
        return self._pca.explained_variance_ratio_

    @property
    def total_explained_variance(self) -> float | None:
        """Return total explained variance."""
        if self._pca is None:
            return None
        return float(np.sum(self._pca.explained_variance_ratio_))

    @property
    def n_components_fitted(self) -> int | None:
        """Return number of components fitted."""
        if self._pca is None:
            return None
        return self._pca.n_components_

    def _flatten_windows(self, windows: np.ndarray) -> np.ndarray:
        """Flatten 3D windows to 2D."""
        if windows.ndim == 3:
            return windows.reshape(windows.shape[0], -1)
        return windows

    def fit(self, windows: np.ndarray) -> "PCAStateExtractor":
        """Fit PCA on training windows.

        Args:
            windows: Array of shape (n_samples, window_size, n_features)
                     or (n_samples, n_flat_features)

        Returns:
            self (for method chaining)
        """
        flat = self._flatten_windows(windows)

        self._pca = PCA(n_components=self.n_components, whiten=self.whiten)
        self._pca.fit(flat)
        self._is_fitted = True

        return self

    def transform(self, windows: np.ndarray) -> np.ndarray:
        """Transform windows to state vectors.

        Args:
            windows: Array of shape (n_samples, window_size, n_features)
                     or (n_samples, n_flat_features)

        Returns:
            State vectors of shape (n_samples, n_components)
        """
        if not self._is_fitted:
            raise RuntimeError("Extractor must be fitted before transform")

        flat = self._flatten_windows(windows)
        return self._pca.transform(flat).astype(np.float32)

    def fit_transform(self, windows: np.ndarray) -> np.ndarray:
        """Fit and transform in one step.

        Args:
            windows: Array of shape (n_samples, window_size, n_features)

        Returns:
            State vectors
        """
        return self.fit(windows).transform(windows)

    def inverse_transform(self, states: np.ndarray) -> np.ndarray:
        """Reconstruct windows from state vectors.

        Args:
            states: State vectors of shape (n_samples, n_components)

        Returns:
            Reconstructed flattened windows (n_samples, window_size * n_features)
        """
        if not self._is_fitted:
            raise RuntimeError("Extractor must be fitted before inverse_transform")

        return self._pca.inverse_transform(states)

    def get_component_importance(self) -> list[tuple[int, float]]:
        """Get component indices sorted by explained variance.

        Returns:
            List of (component_index, variance_ratio) tuples
        """
        if not self._is_fitted:
            return []

        ratios = self._pca.explained_variance_ratio_
        return [(i, float(r)) for i, r in enumerate(ratios)]

    def save(self, path: str) -> None:
        """Save fitted PCA model.

        Args:
            path: Path to save the model
        """
        if not self._is_fitted:
            raise RuntimeError("Cannot save unfitted extractor")

        import joblib

        joblib.dump(
            {
                "pca": self._pca,
                "n_components": self.n_components,
                "whiten": self.whiten,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> "PCAStateExtractor":
        """Load a saved PCA model.

        Args:
            path: Path to the saved model

        Returns:
            Loaded PCAStateExtractor
        """
        import joblib

        data = joblib.load(path)
        extractor = cls(n_components=data["n_components"], whiten=data["whiten"])
        extractor._pca = data["pca"]
        extractor._is_fitted = True
        return extractor
