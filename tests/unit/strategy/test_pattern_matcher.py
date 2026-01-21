"""Tests for pattern matcher."""

import numpy as np
import pytest

from src.strategy.pattern_matcher import PatternMatcher, PatternMatchConfig, PatternMatch


class TestPatternMatchConfig:
    """Tests for PatternMatchConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = PatternMatchConfig()
        assert config.k_neighbors == 10
        assert config.distance_metric == "l2"
        assert config.backend == "auto"

    def test_custom_config(self):
        """Test custom configuration."""
        config = PatternMatchConfig(
            k_neighbors=20,
            distance_metric="cosine",
            backend="sklearn",
        )
        assert config.k_neighbors == 20
        assert config.distance_metric == "cosine"
        assert config.backend == "sklearn"


class TestPatternMatcher:
    """Tests for PatternMatcher."""

    def test_init_default(self):
        """Test default initialization."""
        matcher = PatternMatcher()
        assert not matcher.is_fitted
        assert matcher.n_patterns == 0

    def test_init_sklearn_backend(self):
        """Test initialization with sklearn backend."""
        config = PatternMatchConfig(backend="sklearn")
        matcher = PatternMatcher(config)
        assert matcher._backend == "sklearn"

    def test_fit(self, sample_states, sample_returns):
        """Test fitting the pattern matcher."""
        matcher = PatternMatcher()
        matcher.fit(sample_states, sample_returns)

        assert matcher.is_fitted
        assert matcher.n_patterns == len(sample_states)

    def test_fit_length_mismatch(self, sample_states, sample_returns):
        """Test that fit raises on length mismatch."""
        matcher = PatternMatcher()
        with pytest.raises(ValueError, match="same length"):
            matcher.fit(sample_states, sample_returns[:50])

    def test_query_unfitted_raises(self, sample_states):
        """Test that query on unfitted matcher raises."""
        matcher = PatternMatcher()
        with pytest.raises(RuntimeError, match="must be fitted"):
            matcher.query(sample_states[0])

    def test_query_returns_pattern_match(self, sample_states, sample_returns):
        """Test query returns PatternMatch object."""
        matcher = PatternMatcher()
        matcher.fit(sample_states, sample_returns)

        result = matcher.query(sample_states[0])
        assert isinstance(result, PatternMatch)
        assert len(result.indices) <= matcher.config.k_neighbors
        assert len(result.distances) == len(result.indices)
        assert len(result.returns) == len(result.indices)

    def test_query_1d_state(self, sample_states, sample_returns):
        """Test query with 1D state vector."""
        matcher = PatternMatcher()
        matcher.fit(sample_states, sample_returns)

        # 1D input should work
        state = sample_states[0]  # Shape (16,)
        result = matcher.query(state)
        assert isinstance(result, PatternMatch)

    def test_query_2d_state(self, sample_states, sample_returns):
        """Test query with 2D state vector."""
        matcher = PatternMatcher()
        matcher.fit(sample_states, sample_returns)

        # 2D input should work
        state = sample_states[0:1]  # Shape (1, 16)
        result = matcher.query(state)
        assert isinstance(result, PatternMatch)

    def test_expected_return_calculation(self, sample_states, sample_returns):
        """Test expected return calculation."""
        matcher = PatternMatcher()
        matcher.fit(sample_states, sample_returns)

        result = matcher.query(sample_states[0])
        # Expected return should be within reasonable range
        assert -1.0 <= result.expected_return <= 1.0

    def test_confidence_calculation(self, sample_states, sample_returns):
        """Test confidence calculation."""
        matcher = PatternMatcher()
        matcher.fit(sample_states, sample_returns)

        result = matcher.query(sample_states[0])
        # Confidence should be between 0 and 1
        assert 0.0 <= result.confidence <= 1.0

    def test_win_rate_calculation(self, sample_states, sample_returns):
        """Test win rate calculation."""
        matcher = PatternMatcher()
        matcher.fit(sample_states, sample_returns)

        result = matcher.query(sample_states[0])
        # Win rate should be between 0 and 1
        assert 0.0 <= result.win_rate <= 1.0

    def test_k_neighbors_capped(self, sample_states, sample_returns):
        """Test that k_neighbors is capped by available patterns."""
        config = PatternMatchConfig(k_neighbors=200)  # More than 100 samples
        matcher = PatternMatcher(config)
        matcher.fit(sample_states, sample_returns)

        result = matcher.query(sample_states[0])
        assert len(result.indices) <= len(sample_states)

    def test_distance_threshold(self, sample_states, sample_returns):
        """Test distance threshold filtering."""
        config = PatternMatchConfig(distance_threshold=0.001)  # Very strict
        matcher = PatternMatcher(config)
        matcher.fit(sample_states, sample_returns)

        result = matcher.query(sample_states[0])
        # Should filter out some matches (or all if too strict)
        for dist in result.distances:
            assert dist <= 0.001

    def test_query_batch(self, sample_states, sample_returns):
        """Test batch query."""
        matcher = PatternMatcher()
        matcher.fit(sample_states, sample_returns)

        results = matcher.query_batch(sample_states[:5])
        assert len(results) == 5
        assert all(isinstance(r, PatternMatch) for r in results)

    def test_weight_by_distance(self, sample_states, sample_returns):
        """Test distance-weighted expected return."""
        config = PatternMatchConfig(weight_by_distance=True)
        matcher_weighted = PatternMatcher(config)
        matcher_weighted.fit(sample_states, sample_returns)

        config_unweighted = PatternMatchConfig(weight_by_distance=False)
        matcher_unweighted = PatternMatcher(config_unweighted)
        matcher_unweighted.fit(sample_states, sample_returns)

        # Results should be different
        result_w = matcher_weighted.query(sample_states[50])
        result_u = matcher_unweighted.query(sample_states[50])

        # Both should work, values may differ
        assert result_w.expected_return is not None
        assert result_u.expected_return is not None

    def test_cosine_distance(self, sample_states, sample_returns):
        """Test cosine distance metric."""
        config = PatternMatchConfig(distance_metric="cosine", backend="sklearn")
        matcher = PatternMatcher(config)
        matcher.fit(sample_states, sample_returns)

        result = matcher.query(sample_states[0])
        assert isinstance(result, PatternMatch)

    def test_get_return_distribution(self, sample_states, sample_returns):
        """Test get_return_distribution method."""
        matcher = PatternMatcher()
        matcher.fit(sample_states, sample_returns)

        bin_edges, counts = matcher.get_return_distribution(sample_states[0])
        assert len(bin_edges) > 0 or len(counts) == 0


class TestPatternMatch:
    """Tests for PatternMatch dataclass."""

    def test_pattern_match_creation(self):
        """Test PatternMatch creation."""
        match = PatternMatch(
            indices=np.array([0, 1, 2]),
            distances=np.array([0.1, 0.2, 0.3]),
            returns=np.array([0.01, -0.005, 0.02]),
            expected_return=0.008,
            confidence=0.7,
            win_rate=0.67,
        )
        assert len(match.indices) == 3
        assert match.expected_return == 0.008
        assert match.confidence == 0.7
        assert match.win_rate == 0.67
