"""Tests for HMM model wrapper."""

import numpy as np
import pytest

try:
    from hmmlearn import hmm
    HAS_HMMLEARN = True
except ImportError:
    HAS_HMMLEARN = False

from src.features.state.hmm.hmm_model import (
    GaussianHMMWrapper,
    match_states_hungarian,
    select_n_states,
)


@pytest.mark.skipif(not HAS_HMMLEARN, reason="hmmlearn not installed")
class TestGaussianHMMWrapper:
    """Tests for GaussianHMMWrapper."""

    @pytest.fixture
    def sample_latent(self) -> np.ndarray:
        """Generate sample latent vectors with clear clusters."""
        np.random.seed(42)
        cluster1 = np.random.randn(50, 4) + np.array([2, 0, 0, 0])
        cluster2 = np.random.randn(50, 4) + np.array([-2, 0, 0, 0])
        cluster3 = np.random.randn(50, 4) + np.array([0, 2, 0, 0])
        return np.vstack([cluster1, cluster2, cluster3])

    def test_fit_basic(self, sample_latent: np.ndarray):
        """Test basic model fitting."""
        wrapper = GaussianHMMWrapper(
            n_states=3,
            covariance_type="diag",
            n_iter=50,
            random_state=42,
        )
        wrapper.fit(sample_latent)

        assert wrapper.model_ is not None
        assert wrapper.latent_dim == 4
        assert wrapper.metrics_ is not None

    def test_predict(self, sample_latent: np.ndarray):
        """Test state prediction."""
        wrapper = GaussianHMMWrapper(n_states=3, random_state=42)
        wrapper.fit(sample_latent)
        states = wrapper.predict(sample_latent)

        assert states.shape == (150,)
        assert set(states).issubset({0, 1, 2})

    def test_predict_proba(self, sample_latent: np.ndarray):
        """Test posterior probability computation."""
        wrapper = GaussianHMMWrapper(n_states=3, random_state=42)
        wrapper.fit(sample_latent)
        probs = wrapper.predict_proba(sample_latent)

        assert probs.shape == (150, 3)
        assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-6)
        assert np.all(probs >= 0)
        assert np.all(probs <= 1)

    def test_emission_log_likelihood(self, sample_latent: np.ndarray):
        """Test emission log-likelihood computation."""
        wrapper = GaussianHMMWrapper(n_states=3, random_state=42)
        wrapper.fit(sample_latent)
        log_liks = wrapper.emission_log_likelihood(sample_latent)

        assert log_liks.shape == (150,)
        assert np.all(np.isfinite(log_liks))

    def test_nan_handling(self, sample_latent: np.ndarray):
        """Test handling of NaN values."""
        wrapper = GaussianHMMWrapper(n_states=3, random_state=42)
        wrapper.fit(sample_latent)

        Z_with_nan = sample_latent.copy()
        Z_with_nan[0, 0] = np.nan

        states = wrapper.predict(Z_with_nan)
        assert states[0] == -1
        assert states[1] != -1

    def test_metrics_computed(self, sample_latent: np.ndarray):
        """Test that metrics are computed after fit."""
        wrapper = GaussianHMMWrapper(n_states=3, random_state=42)
        wrapper.fit(sample_latent)

        assert wrapper.metrics_.log_likelihood is not None
        assert wrapper.metrics_.aic is not None
        assert wrapper.metrics_.bic is not None
        assert len(wrapper.metrics_.mean_dwell_time) == 3
        assert len(wrapper.metrics_.state_occupancy) == 3

    def test_transition_matrix_diagonal_bias(self, sample_latent: np.ndarray):
        """Test that transition matrix has diagonal bias."""
        wrapper = GaussianHMMWrapper(
            n_states=3,
            diagonal_bias=0.9,
            random_state=42,
        )
        wrapper.fit(sample_latent)

        diag = np.diag(wrapper.transition_matrix)
        assert np.all(diag > 0.5)

    def test_covariance_regularization(self, sample_latent: np.ndarray):
        """Test covariance regularization."""
        wrapper = GaussianHMMWrapper(
            n_states=3,
            covariance_type="diag",
            cov_reg=1e-3,
            random_state=42,
        )
        wrapper.fit(sample_latent)

        assert np.all(wrapper.covariances >= 1e-3)

    def test_properties(self, sample_latent: np.ndarray):
        """Test model properties."""
        wrapper = GaussianHMMWrapper(n_states=3, random_state=42)
        wrapper.fit(sample_latent)

        assert wrapper.transition_matrix.shape == (3, 3)
        assert wrapper.means.shape == (3, 4)

    def test_unfitted_raises(self):
        """Test that methods raise error when not fitted."""
        wrapper = GaussianHMMWrapper(n_states=3)

        with pytest.raises(ValueError, match="not fitted"):
            wrapper.predict(np.random.randn(10, 4))


@pytest.mark.skipif(not HAS_HMMLEARN, reason="hmmlearn not installed")
class TestSelectNStates:
    """Tests for select_n_states utility."""

    def test_basic_selection(self):
        """Test basic state count selection."""
        np.random.seed(42)
        cluster1 = np.random.randn(100, 4) + np.array([3, 0, 0, 0])
        cluster2 = np.random.randn(100, 4) + np.array([-3, 0, 0, 0])
        Z = np.vstack([cluster1, cluster2])

        best_k, scores = select_n_states(
            Z,
            state_range=range(2, 6),
            criterion="bic",
            random_state=42,
        )

        assert 2 <= best_k <= 5
        assert len(scores) >= 1


class TestMatchStatesHungarian:
    """Tests for Hungarian state matching."""

    def test_perfect_match(self):
        """Test matching identical means."""
        old_means = np.array([[0, 0], [1, 0], [0, 1]])
        new_means = old_means.copy()

        mapping = match_states_hungarian(old_means, new_means)

        assert mapping == {0: 0, 1: 1, 2: 2}

    def test_permuted_match(self):
        """Test matching permuted means."""
        old_means = np.array([[0, 0], [1, 0], [0, 1]])
        new_means = np.array([[1, 0], [0, 1], [0, 0]])

        mapping = match_states_hungarian(old_means, new_means)

        assert mapping[0] == 1
        assert mapping[1] == 2
        assert mapping[2] == 0

    def test_noisy_match(self):
        """Test matching with small noise."""
        np.random.seed(42)
        old_means = np.array([[0, 0], [5, 0], [0, 5]])
        new_means = old_means + np.random.randn(3, 2) * 0.1

        mapping = match_states_hungarian(old_means, new_means)

        assert mapping == {0: 0, 1: 1, 2: 2}
