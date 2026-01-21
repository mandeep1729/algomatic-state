"""Regime clustering for state-based trading."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture


@dataclass
class ClusteringConfig:
    """Configuration for regime clustering.

    Attributes:
        n_clusters: Number of regimes to identify
        method: Clustering method (kmeans or gmm)
        random_state: Random seed for reproducibility
    """

    n_clusters: int = 5
    method: Literal["kmeans", "gmm"] = "kmeans"
    random_state: int = 42


@dataclass
class RegimeInfo:
    """Information about a detected regime.

    Attributes:
        label: Regime identifier
        center: Cluster center in latent space
        size: Number of samples in this regime
        mean_return: Average forward return
        std_return: Standard deviation of returns
        sharpe: Sharpe ratio approximation
    """

    label: int
    center: np.ndarray
    size: int
    mean_return: float = 0.0
    std_return: float = 0.0
    sharpe: float = 0.0


class RegimeClusterer:
    """Cluster state vectors into trading regimes.

    Supports:
    - K-means clustering
    - Gaussian Mixture Models (GMM)
    - Regime performance labeling
    - Transition probability analysis

    Example:
        >>> clusterer = RegimeClusterer(n_clusters=5)
        >>> clusterer.fit(train_states, train_returns)
        >>> labels = clusterer.predict(new_states)
        >>> favorable = clusterer.get_favorable_regimes()
    """

    def __init__(
        self,
        n_clusters: int = 5,
        method: Literal["kmeans", "gmm"] = "kmeans",
        random_state: int = 42,
    ):
        """Initialize RegimeClusterer.

        Args:
            n_clusters: Number of regimes to identify
            method: Clustering method
            random_state: Random seed
        """
        self.n_clusters = n_clusters
        self.method = method
        self.random_state = random_state

        self._model: KMeans | GaussianMixture | None = None
        self._regime_info: dict[int, RegimeInfo] = {}
        self._transition_matrix: np.ndarray | None = None
        self._is_fitted = False

    @property
    def config(self) -> ClusteringConfig:
        """Return current configuration."""
        return ClusteringConfig(
            n_clusters=self.n_clusters,
            method=self.method,
            random_state=self.random_state,
        )

    @property
    def is_fitted(self) -> bool:
        """Check if clusterer has been fitted."""
        return self._is_fitted

    @property
    def regime_info(self) -> dict[int, RegimeInfo]:
        """Get regime information."""
        return self._regime_info

    @property
    def transition_matrix(self) -> np.ndarray | None:
        """Get regime transition probability matrix."""
        return self._transition_matrix

    def fit(
        self, states: np.ndarray, returns: np.ndarray | None = None
    ) -> "RegimeClusterer":
        """Fit clustering model on state vectors.

        Args:
            states: State vectors (n_samples, latent_dim)
            returns: Optional forward returns for regime labeling

        Returns:
            self (for method chaining)
        """
        # Create and fit clustering model
        if self.method == "kmeans":
            self._model = KMeans(
                n_clusters=self.n_clusters,
                random_state=self.random_state,
                n_init=10,
            )
        else:
            self._model = GaussianMixture(
                n_components=self.n_clusters,
                random_state=self.random_state,
                n_init=5,
            )

        labels = self._model.fit_predict(states)

        # Compute regime statistics
        self._compute_regime_info(states, labels, returns)

        # Compute transition matrix
        self._compute_transitions(labels)

        self._is_fitted = True
        return self

    def _compute_regime_info(
        self,
        states: np.ndarray,
        labels: np.ndarray,
        returns: np.ndarray | None,
    ) -> None:
        """Compute information for each regime."""
        self._regime_info = {}

        for label in range(self.n_clusters):
            mask = labels == label
            regime_states = states[mask]

            # Cluster center
            if self.method == "kmeans":
                center = self._model.cluster_centers_[label]
            else:
                center = self._model.means_[label]

            info = RegimeInfo(
                label=label,
                center=center,
                size=int(np.sum(mask)),
            )

            # Add return statistics if available
            if returns is not None and np.sum(mask) > 0:
                regime_returns = returns[mask]
                info.mean_return = float(np.mean(regime_returns))
                info.std_return = float(np.std(regime_returns))
                if info.std_return > 1e-8:
                    # Annualized Sharpe
                    info.sharpe = info.mean_return / info.std_return * np.sqrt(252 * 390)

            self._regime_info[label] = info

    def _compute_transitions(self, labels: np.ndarray) -> None:
        """Compute regime transition probability matrix."""
        trans = np.zeros((self.n_clusters, self.n_clusters))

        for i in range(len(labels) - 1):
            from_regime = labels[i]
            to_regime = labels[i + 1]
            trans[from_regime, to_regime] += 1

        # Normalize to probabilities
        row_sums = trans.sum(axis=1, keepdims=True)
        row_sums = np.where(row_sums == 0, 1, row_sums)
        self._transition_matrix = trans / row_sums

    def predict(self, states: np.ndarray) -> np.ndarray:
        """Predict regime labels for new states.

        Args:
            states: State vectors (n_samples, latent_dim)

        Returns:
            Regime labels (n_samples,)
        """
        if not self._is_fitted:
            raise RuntimeError("Clusterer must be fitted before predict")

        return self._model.predict(states)

    def predict_proba(self, states: np.ndarray) -> np.ndarray | None:
        """Predict regime probabilities (GMM only).

        Args:
            states: State vectors (n_samples, latent_dim)

        Returns:
            Probability matrix (n_samples, n_clusters) or None if using kmeans
        """
        if not self._is_fitted:
            raise RuntimeError("Clusterer must be fitted before predict_proba")

        if self.method != "gmm":
            return None

        return self._model.predict_proba(states)

    def get_favorable_regimes(self, min_sharpe: float = 0.0) -> list[int]:
        """Get list of favorable regimes based on Sharpe ratio.

        Args:
            min_sharpe: Minimum Sharpe ratio to consider favorable

        Returns:
            List of favorable regime labels
        """
        return [
            label
            for label, info in self._regime_info.items()
            if info.sharpe > min_sharpe
        ]

    def get_unfavorable_regimes(self, max_sharpe: float = 0.0) -> list[int]:
        """Get list of unfavorable regimes.

        Args:
            max_sharpe: Maximum Sharpe ratio to consider unfavorable

        Returns:
            List of unfavorable regime labels
        """
        return [
            label
            for label, info in self._regime_info.items()
            if info.sharpe < max_sharpe
        ]

    def is_favorable(self, state: np.ndarray, min_sharpe: float = 0.0) -> bool:
        """Check if current state is in a favorable regime.

        Args:
            state: Single state vector (latent_dim,) or (1, latent_dim)
            min_sharpe: Minimum Sharpe ratio threshold

        Returns:
            True if in favorable regime
        """
        if state.ndim == 1:
            state = state.reshape(1, -1)

        label = self.predict(state)[0]
        return bool(self._regime_info[label].sharpe > min_sharpe)

    def get_regime_summary(self) -> list[dict]:
        """Get summary of all regimes sorted by Sharpe ratio.

        Returns:
            List of regime dictionaries sorted by performance
        """
        summaries = []
        for info in self._regime_info.values():
            summaries.append(
                {
                    "label": info.label,
                    "size": info.size,
                    "mean_return": info.mean_return,
                    "std_return": info.std_return,
                    "sharpe": info.sharpe,
                }
            )

        return sorted(summaries, key=lambda x: x["sharpe"], reverse=True)

    def save(self, path: str) -> None:
        """Save fitted model.

        Args:
            path: Path to save model
        """
        if not self._is_fitted:
            raise RuntimeError("Cannot save unfitted clusterer")

        import joblib

        joblib.dump(
            {
                "model": self._model,
                "regime_info": self._regime_info,
                "transition_matrix": self._transition_matrix,
                "config": self.config,
            },
            path,
        )

    @classmethod
    def load(cls, path: str) -> "RegimeClusterer":
        """Load a saved clusterer.

        Args:
            path: Path to saved model

        Returns:
            Loaded RegimeClusterer
        """
        import joblib

        data = joblib.load(path)
        config = data["config"]
        clusterer = cls(
            n_clusters=config.n_clusters,
            method=config.method,
            random_state=config.random_state,
        )
        clusterer._model = data["model"]
        clusterer._regime_info = data["regime_info"]
        clusterer._transition_matrix = data["transition_matrix"]
        clusterer._is_fitted = True
        return clusterer
