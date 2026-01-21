"""State quality validation metrics."""

from dataclasses import dataclass

import numpy as np
from sklearn.metrics import calinski_harabasz_score, silhouette_score


@dataclass
class ReconstructionMetrics:
    """Reconstruction quality metrics.

    Attributes:
        mse: Mean squared error
        mae: Mean absolute error
        per_feature_mse: MSE per feature
    """

    mse: float
    mae: float
    per_feature_mse: np.ndarray


@dataclass
class ClusterMetrics:
    """Clustering quality metrics.

    Attributes:
        silhouette: Silhouette score (-1 to 1, higher is better)
        calinski_harabasz: Calinski-Harabasz index (higher is better)
        n_clusters: Number of clusters
    """

    silhouette: float
    calinski_harabasz: float
    n_clusters: int


@dataclass
class TemporalMetrics:
    """Temporal stability metrics.

    Attributes:
        mean_transition: Mean state transition magnitude
        std_transition: Std of state transitions
        smoothness: Smoothness score (1 - normalized mean transition)
    """

    mean_transition: float
    std_transition: float
    smoothness: float


class StateValidator:
    """Validate quality of learned state representations.

    Computes:
    - Reconstruction metrics (MSE, MAE, per-feature error)
    - Cluster analysis (silhouette score, Calinski-Harabasz)
    - Temporal stability (state transition smoothness)

    Example:
        >>> validator = StateValidator()
        >>> recon_metrics = validator.compute_reconstruction_metrics(x, x_hat)
        >>> cluster_metrics = validator.compute_cluster_metrics(states, labels)
    """

    def compute_reconstruction_metrics(
        self, original: np.ndarray, reconstructed: np.ndarray
    ) -> ReconstructionMetrics:
        """Compute reconstruction quality metrics.

        Args:
            original: Original windows (n_samples, window_size, n_features)
            reconstructed: Reconstructed windows (same shape)

        Returns:
            ReconstructionMetrics object
        """
        # Flatten for overall metrics
        diff = original - reconstructed
        mse = float(np.mean(diff**2))
        mae = float(np.mean(np.abs(diff)))

        # Per-feature MSE (aggregate over samples and time)
        if original.ndim == 3:
            per_feature_mse = np.mean(diff**2, axis=(0, 1))
        else:
            per_feature_mse = np.mean(diff**2, axis=0)

        return ReconstructionMetrics(mse=mse, mae=mae, per_feature_mse=per_feature_mse)

    def compute_cluster_metrics(
        self, states: np.ndarray, labels: np.ndarray
    ) -> ClusterMetrics:
        """Compute clustering quality metrics.

        Args:
            states: State vectors (n_samples, latent_dim)
            labels: Cluster labels (n_samples,)

        Returns:
            ClusterMetrics object
        """
        n_clusters = len(np.unique(labels))

        # Need at least 2 clusters for these metrics
        if n_clusters < 2:
            return ClusterMetrics(
                silhouette=0.0, calinski_harabasz=0.0, n_clusters=n_clusters
            )

        silhouette = float(silhouette_score(states, labels))
        calinski = float(calinski_harabasz_score(states, labels))

        return ClusterMetrics(
            silhouette=silhouette, calinski_harabasz=calinski, n_clusters=n_clusters
        )

    def compute_temporal_metrics(self, states: np.ndarray) -> TemporalMetrics:
        """Compute temporal stability metrics.

        Measures how smoothly states transition over time.

        Args:
            states: State vectors in temporal order (n_samples, latent_dim)

        Returns:
            TemporalMetrics object
        """
        # Compute state transitions (consecutive differences)
        transitions = np.diff(states, axis=0)
        transition_magnitudes = np.linalg.norm(transitions, axis=1)

        mean_transition = float(np.mean(transition_magnitudes))
        std_transition = float(np.std(transition_magnitudes))

        # Normalize smoothness to [0, 1] where 1 is perfectly smooth
        # Use the average state magnitude as reference
        state_magnitudes = np.linalg.norm(states, axis=1)
        avg_state_mag = np.mean(state_magnitudes)

        if avg_state_mag > 1e-8:
            smoothness = 1.0 - min(1.0, mean_transition / avg_state_mag)
        else:
            smoothness = 1.0

        return TemporalMetrics(
            mean_transition=mean_transition,
            std_transition=std_transition,
            smoothness=smoothness,
        )

    def compute_regime_purity(
        self, labels: np.ndarray, returns: np.ndarray
    ) -> dict[int, dict[str, float]]:
        """Compute regime purity based on return distributions.

        Args:
            labels: Cluster/regime labels (n_samples,)
            returns: Forward returns for each sample (n_samples,)

        Returns:
            Dictionary mapping regime -> {mean_return, std_return, sharpe, count}
        """
        regime_stats = {}
        unique_labels = np.unique(labels)

        for label in unique_labels:
            mask = labels == label
            regime_returns = returns[mask]

            mean_ret = float(np.mean(regime_returns))
            std_ret = float(np.std(regime_returns))

            # Annualized Sharpe approximation (assuming 1-min returns)
            # sqrt(252 * 390) for annualization
            sharpe = mean_ret / std_ret * np.sqrt(252 * 390) if std_ret > 1e-8 else 0.0

            regime_stats[int(label)] = {
                "mean_return": mean_ret,
                "std_return": std_ret,
                "sharpe": sharpe,
                "count": int(np.sum(mask)),
            }

        return regime_stats

    def compare_methods(
        self,
        original: np.ndarray,
        pca_reconstructed: np.ndarray,
        ae_reconstructed: np.ndarray,
    ) -> dict[str, ReconstructionMetrics]:
        """Compare reconstruction quality between PCA and autoencoder.

        Args:
            original: Original windows
            pca_reconstructed: PCA reconstructed windows
            ae_reconstructed: Autoencoder reconstructed windows

        Returns:
            Dictionary with metrics for each method
        """
        return {
            "pca": self.compute_reconstruction_metrics(original, pca_reconstructed),
            "autoencoder": self.compute_reconstruction_metrics(
                original, ae_reconstructed
            ),
        }
