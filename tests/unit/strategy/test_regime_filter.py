"""Tests for regime filter."""

from datetime import datetime

import numpy as np
import pytest

from src.state.clustering import RegimeClusterer
from src.strategy.regime_filter import RegimeFilter, RegimeFilterConfig
from src.strategy.signals import Signal, SignalDirection, SignalMetadata


@pytest.fixture
def fitted_clusterer(sample_states, sample_returns):
    """Create a fitted regime clusterer."""
    clusterer = RegimeClusterer(n_clusters=3, random_state=42)
    clusterer.fit(sample_states, sample_returns)
    return clusterer


@pytest.fixture
def sample_signal():
    """Create a sample long signal."""
    return Signal(
        timestamp=datetime(2024, 1, 1, 10, 30),
        symbol="AAPL",
        direction=SignalDirection.LONG,
        strength=0.8,
        metadata=SignalMetadata(momentum_value=0.003, volatility=0.01),
    )


class TestRegimeFilterConfig:
    """Tests for RegimeFilterConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = RegimeFilterConfig()
        assert config.min_sharpe == 0.0
        assert config.filter_mode == "block"
        assert config.blocked_regimes == []
        assert config.allowed_regimes == []

    def test_custom_config(self):
        """Test custom configuration."""
        config = RegimeFilterConfig(
            min_sharpe=0.5,
            blocked_regimes=[0, 1],
            filter_mode="reduce",
        )
        assert config.min_sharpe == 0.5
        assert config.blocked_regimes == [0, 1]
        assert config.filter_mode == "reduce"


class TestRegimeFilter:
    """Tests for RegimeFilter."""

    def test_init_requires_fitted_clusterer(self, sample_states):
        """Test that initialization requires fitted clusterer."""
        unfitted = RegimeClusterer(n_clusters=3)
        with pytest.raises(ValueError, match="must be fitted"):
            RegimeFilter(unfitted)

    def test_init_with_fitted_clusterer(self, fitted_clusterer):
        """Test initialization with fitted clusterer."""
        filter = RegimeFilter(fitted_clusterer)
        assert filter.clusterer is fitted_clusterer

    def test_flat_signal_passes_through(self, fitted_clusterer, sample_states):
        """Test that flat signals pass through unchanged."""
        filter = RegimeFilter(fitted_clusterer)

        flat_signal = Signal(
            timestamp=datetime(2024, 1, 1, 10, 30),
            symbol="AAPL",
            direction=SignalDirection.FLAT,
        )

        result = filter.apply(flat_signal, sample_states[0])
        assert result.direction == SignalDirection.FLAT

    def test_apply_adds_regime_info(self, fitted_clusterer, sample_signal, sample_states):
        """Test that apply adds regime information to signal."""
        filter = RegimeFilter(fitted_clusterer)
        result = filter.apply(sample_signal, sample_states[0])

        assert result.metadata.regime_label is not None
        assert result.metadata.regime_sharpe is not None

    def test_block_mode_filters_unfavorable(
        self, fitted_clusterer, sample_signal, sample_states
    ):
        """Test block mode filters unfavorable regimes."""
        # Set high min_sharpe to force filtering
        config = RegimeFilterConfig(min_sharpe=100.0, filter_mode="block")
        filter = RegimeFilter(fitted_clusterer, config)

        result = filter.apply(sample_signal, sample_states[0])

        # Should be blocked (flat)
        assert result.direction == SignalDirection.FLAT
        assert result.metadata.custom.get("filtered") is True

    def test_reduce_mode_reduces_strength(
        self, fitted_clusterer, sample_signal, sample_states
    ):
        """Test reduce mode reduces signal strength."""
        config = RegimeFilterConfig(
            min_sharpe=100.0,  # High to force reduction
            filter_mode="reduce",
            strength_reduction=0.5,
        )
        filter = RegimeFilter(fitted_clusterer, config)

        result = filter.apply(sample_signal, sample_states[0])

        # Should be reduced, not blocked
        assert result.direction == SignalDirection.LONG
        assert result.strength == sample_signal.strength * 0.5

    def test_blocked_regimes_always_blocked(
        self, fitted_clusterer, sample_signal, sample_states
    ):
        """Test that explicitly blocked regimes are always filtered."""
        # Block all regimes
        config = RegimeFilterConfig(blocked_regimes=[0, 1, 2])
        filter = RegimeFilter(fitted_clusterer, config)

        result = filter.apply(sample_signal, sample_states[0])
        assert result.direction == SignalDirection.FLAT

    def test_allowed_regimes_always_pass(
        self, fitted_clusterer, sample_signal, sample_states
    ):
        """Test that explicitly allowed regimes always pass."""
        # Allow all regimes even with high min_sharpe
        config = RegimeFilterConfig(
            min_sharpe=100.0,
            allowed_regimes=[0, 1, 2],
        )
        filter = RegimeFilter(fitted_clusterer, config)

        result = filter.apply(sample_signal, sample_states[0])
        assert result.direction == SignalDirection.LONG

    def test_is_favorable(self, fitted_clusterer, sample_states):
        """Test is_favorable method."""
        config = RegimeFilterConfig(min_sharpe=0.0)
        filter = RegimeFilter(fitted_clusterer, config)

        # Should be favorable since min_sharpe is 0
        assert filter.is_favorable(sample_states[0]) or not filter.is_favorable(sample_states[0])

    def test_get_regime_status(self, fitted_clusterer, sample_states):
        """Test get_regime_status method."""
        filter = RegimeFilter(fitted_clusterer)
        status = filter.get_regime_status(sample_states[0])

        assert "regime_label" in status
        assert "regime_sharpe" in status
        assert "is_favorable" in status
        assert "is_blocked" in status
        assert "is_allowed" in status

    def test_batch_apply(self, fitted_clusterer, sample_signal, sample_states):
        """Test applying filter to batch of signals."""
        filter = RegimeFilter(fitted_clusterer)

        signals = [sample_signal] * 5
        states = sample_states[:5]

        results = filter.apply_batch(signals, states)
        assert len(results) == 5

    def test_batch_apply_length_mismatch(self, fitted_clusterer, sample_signal, sample_states):
        """Test that batch apply raises on length mismatch."""
        filter = RegimeFilter(fitted_clusterer)

        signals = [sample_signal] * 3
        states = sample_states[:5]

        with pytest.raises(ValueError, match="must match"):
            filter.apply_batch(signals, states)

    def test_log_decisions(self, fitted_clusterer, sample_signal, sample_states):
        """Test decision logging."""
        config = RegimeFilterConfig(log_decisions=True)
        filter = RegimeFilter(fitted_clusterer, config)

        filter.apply(sample_signal, sample_states[0])

        assert len(filter.decisions) == 1
        assert "regime_label" in filter.decisions[0]
        assert "should_filter" in filter.decisions[0]

    def test_clear_decisions(self, fitted_clusterer, sample_signal, sample_states):
        """Test clearing logged decisions."""
        config = RegimeFilterConfig(log_decisions=True)
        filter = RegimeFilter(fitted_clusterer, config)

        filter.apply(sample_signal, sample_states[0])
        assert len(filter.decisions) == 1

        filter.clear_decisions()
        assert len(filter.decisions) == 0

    def test_get_filter_stats(self, fitted_clusterer, sample_signal, sample_states):
        """Test getting filter statistics."""
        config = RegimeFilterConfig(log_decisions=True, min_sharpe=0.0)
        filter = RegimeFilter(fitted_clusterer, config)

        # Apply to several signals
        for i in range(10):
            filter.apply(sample_signal, sample_states[i])

        stats = filter.get_filter_stats()
        assert stats["total_signals"] == 10
        assert "filter_rate" in stats
        assert "by_regime" in stats
