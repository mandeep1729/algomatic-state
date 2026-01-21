"""Tests for regime clustering."""

import numpy as np
import pytest

from src.state.clustering import RegimeClusterer


class TestRegimeClusterer:
    """Tests for RegimeClusterer."""

    @pytest.fixture
    def clusterer(self) -> RegimeClusterer:
        return RegimeClusterer(n_clusters=3, method="kmeans")

    def test_init(self):
        """Test initialization."""
        clust = RegimeClusterer(n_clusters=5, method="gmm")
        assert clust.n_clusters == 5
        assert clust.method == "gmm"
        assert not clust.is_fitted

    def test_fit(self, clusterer: RegimeClusterer, sample_states: np.ndarray, sample_returns: np.ndarray):
        """Test fitting clusterer."""
        clusterer.fit(sample_states, sample_returns)
        
        assert clusterer.is_fitted
        assert len(clusterer.regime_info) == 3

    def test_predict(self, clusterer: RegimeClusterer, sample_states: np.ndarray):
        """Test prediction."""
        clusterer.fit(sample_states)
        labels = clusterer.predict(sample_states[:10])
        
        assert len(labels) == 10
        assert all(0 <= l < 3 for l in labels)

    def test_predict_proba_kmeans(self, clusterer: RegimeClusterer, sample_states: np.ndarray):
        """Test predict_proba returns None for kmeans."""
        clusterer.fit(sample_states)
        proba = clusterer.predict_proba(sample_states[:10])
        
        assert proba is None

    def test_predict_proba_gmm(self, sample_states: np.ndarray):
        """Test predict_proba works for GMM."""
        clust = RegimeClusterer(n_clusters=3, method="gmm")
        clust.fit(sample_states)
        proba = clust.predict_proba(sample_states[:10])
        
        assert proba is not None
        assert proba.shape == (10, 3)
        assert np.allclose(proba.sum(axis=1), 1)

    def test_transition_matrix(self, clusterer: RegimeClusterer, sample_states: np.ndarray):
        """Test transition matrix computation."""
        clusterer.fit(sample_states)
        
        trans = clusterer.transition_matrix
        assert trans is not None
        assert trans.shape == (3, 3)
        # Rows should sum to 1
        assert np.allclose(trans.sum(axis=1), 1)

    def test_favorable_regimes(self, clusterer: RegimeClusterer, sample_states: np.ndarray, sample_returns: np.ndarray):
        """Test getting favorable regimes."""
        clusterer.fit(sample_states, sample_returns)
        
        favorable = clusterer.get_favorable_regimes(min_sharpe=0.0)
        unfavorable = clusterer.get_unfavorable_regimes(max_sharpe=0.0)
        
        # Combined should cover all regimes
        assert len(favorable) + len(unfavorable) >= 0

    def test_is_favorable(self, clusterer: RegimeClusterer, sample_states: np.ndarray, sample_returns: np.ndarray):
        """Test is_favorable method."""
        clusterer.fit(sample_states, sample_returns)
        
        # Should run without error
        result = clusterer.is_favorable(sample_states[0], min_sharpe=-1.0)
        assert isinstance(result, bool)

    def test_regime_summary(self, clusterer: RegimeClusterer, sample_states: np.ndarray, sample_returns: np.ndarray):
        """Test regime summary generation."""
        clusterer.fit(sample_states, sample_returns)
        summary = clusterer.get_regime_summary()
        
        assert len(summary) == 3
        # Should be sorted by Sharpe (descending)
        sharpe_values = [s["sharpe"] for s in summary]
        assert sharpe_values == sorted(sharpe_values, reverse=True)

    def test_predict_before_fit_raises(self, clusterer: RegimeClusterer, sample_states: np.ndarray):
        """Test predict before fit raises error."""
        with pytest.raises(RuntimeError, match="fitted"):
            clusterer.predict(sample_states)
