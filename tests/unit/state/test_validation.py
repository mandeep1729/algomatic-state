"""Tests for state validation metrics."""

import numpy as np
import pytest

from src.state.validation import StateValidator


class TestStateValidator:
    """Tests for StateValidator."""

    @pytest.fixture
    def validator(self) -> StateValidator:
        return StateValidator()

    def test_reconstruction_metrics(self, validator: StateValidator):
        """Test reconstruction metrics computation."""
        original = np.random.randn(50, 20, 10).astype(np.float32)
        # Add some noise for imperfect reconstruction
        reconstructed = original + np.random.randn(*original.shape) * 0.1
        
        metrics = validator.compute_reconstruction_metrics(original, reconstructed)
        
        assert metrics.mse > 0
        assert metrics.mae > 0
        assert len(metrics.per_feature_mse) == 10

    def test_reconstruction_metrics_perfect(self, validator: StateValidator):
        """Test reconstruction metrics with perfect reconstruction."""
        original = np.random.randn(50, 20, 10).astype(np.float32)
        
        metrics = validator.compute_reconstruction_metrics(original, original)
        
        assert np.isclose(metrics.mse, 0)
        assert np.isclose(metrics.mae, 0)

    def test_cluster_metrics(self, validator: StateValidator, sample_states: np.ndarray):
        """Test cluster metrics computation."""
        # Create some labels
        labels = np.random.randint(0, 3, size=len(sample_states))
        
        metrics = validator.compute_cluster_metrics(sample_states, labels)
        
        assert -1 <= metrics.silhouette <= 1
        assert metrics.calinski_harabasz >= 0
        assert metrics.n_clusters == 3

    def test_cluster_metrics_single_cluster(self, validator: StateValidator, sample_states: np.ndarray):
        """Test cluster metrics with single cluster."""
        labels = np.zeros(len(sample_states), dtype=int)
        
        metrics = validator.compute_cluster_metrics(sample_states, labels)
        
        assert metrics.n_clusters == 1
        assert metrics.silhouette == 0

    def test_temporal_metrics(self, validator: StateValidator, sample_states: np.ndarray):
        """Test temporal stability metrics."""
        metrics = validator.compute_temporal_metrics(sample_states)
        
        assert metrics.mean_transition >= 0
        assert metrics.std_transition >= 0
        assert 0 <= metrics.smoothness <= 1

    def test_regime_purity(self, validator: StateValidator, sample_returns: np.ndarray):
        """Test regime purity computation."""
        labels = np.random.randint(0, 3, size=len(sample_returns))
        
        stats = validator.compute_regime_purity(labels, sample_returns)
        
        assert len(stats) == 3
        for label, info in stats.items():
            assert "mean_return" in info
            assert "sharpe" in info
            assert "count" in info

    def test_compare_methods(self, validator: StateValidator):
        """Test method comparison."""
        original = np.random.randn(50, 20, 10).astype(np.float32)
        pca_recon = original + np.random.randn(*original.shape) * 0.2
        ae_recon = original + np.random.randn(*original.shape) * 0.1
        
        comparison = validator.compare_methods(original, pca_recon, ae_recon)
        
        assert "pca" in comparison
        assert "autoencoder" in comparison
        # AE should have lower error with less noise
        assert comparison["autoencoder"].mse < comparison["pca"].mse
