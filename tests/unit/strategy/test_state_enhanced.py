"""Tests for state-enhanced strategy."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src.state.clustering import RegimeClusterer
from src.strategy.momentum import MomentumConfig
from src.strategy.pattern_matcher import PatternMatcher, PatternMatchConfig
from src.strategy.position_sizer import PositionSizerConfig
from src.strategy.regime_filter import RegimeFilterConfig
from src.strategy.signals import SignalDirection
from src.strategy.state_enhanced import StateEnhancedStrategy, StateEnhancedConfig


@pytest.fixture
def fitted_clusterer(sample_states, sample_returns):
    """Create a fitted regime clusterer."""
    clusterer = RegimeClusterer(n_clusters=3, random_state=42)
    clusterer.fit(sample_states, sample_returns)
    return clusterer


@pytest.fixture
def fitted_matcher(sample_states, sample_returns):
    """Create a fitted pattern matcher."""
    config = PatternMatchConfig(k_neighbors=5, backend="sklearn")
    matcher = PatternMatcher(config)
    matcher.fit(sample_states, sample_returns)
    return matcher


@pytest.fixture
def enhanced_config():
    """Create state-enhanced configuration."""
    return StateEnhancedConfig(
        momentum_config=MomentumConfig(
            symbols=["AAPL"],
            long_threshold=0.001,
            short_threshold=-0.001,
        ),
        regime_filter_config=RegimeFilterConfig(min_sharpe=-10.0),  # Allow most
        pattern_match_config=PatternMatchConfig(k_neighbors=5, backend="sklearn"),
        position_sizer_config=PositionSizerConfig(base_size=10000.0),
        enable_regime_filter=True,
        enable_pattern_matching=True,
        enable_dynamic_sizing=True,
    )


class TestStateEnhancedConfig:
    """Tests for StateEnhancedConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = StateEnhancedConfig()
        assert config.name == "state_enhanced"
        assert config.enable_regime_filter is True
        assert config.enable_pattern_matching is True
        assert config.enable_dynamic_sizing is True

    def test_disable_features(self):
        """Test disabling features."""
        config = StateEnhancedConfig(
            enable_regime_filter=False,
            enable_pattern_matching=False,
            enable_dynamic_sizing=False,
        )
        assert not config.enable_regime_filter
        assert not config.enable_pattern_matching
        assert not config.enable_dynamic_sizing


class TestStateEnhancedStrategy:
    """Tests for StateEnhancedStrategy."""

    def test_init_requires_clusterer_when_enabled(self, fitted_matcher):
        """Test that clusterer is required when regime filter enabled."""
        config = StateEnhancedConfig(
            enable_regime_filter=True,
            enable_pattern_matching=True,
        )
        with pytest.raises(ValueError, match="RegimeClusterer required"):
            StateEnhancedStrategy(config, pattern_matcher=fitted_matcher)

    def test_init_requires_matcher_when_enabled(self, fitted_clusterer):
        """Test that matcher is required when pattern matching enabled."""
        config = StateEnhancedConfig(
            enable_regime_filter=True,
            enable_pattern_matching=True,
        )
        with pytest.raises(ValueError, match="PatternMatcher required"):
            StateEnhancedStrategy(config, clusterer=fitted_clusterer)

    def test_init_all_components(
        self, enhanced_config, fitted_clusterer, fitted_matcher
    ):
        """Test initialization with all components."""
        strategy = StateEnhancedStrategy(
            enhanced_config,
            clusterer=fitted_clusterer,
            pattern_matcher=fitted_matcher,
        )
        assert strategy.regime_filter is not None
        assert strategy.pattern_matcher is not None
        assert strategy.position_sizer is not None

    def test_init_disabled_components(self):
        """Test initialization with disabled components."""
        config = StateEnhancedConfig(
            enable_regime_filter=False,
            enable_pattern_matching=False,
            enable_dynamic_sizing=False,
        )
        strategy = StateEnhancedStrategy(config)
        assert strategy.regime_filter is None
        assert strategy.pattern_matcher is None
        assert strategy.position_sizer is None

    def test_generate_signals_long(
        self,
        enhanced_config,
        fitted_clusterer,
        fitted_matcher,
        sample_features,
        sample_states,
    ):
        """Test generating enhanced long signals."""
        # Set high momentum
        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = 0.005

        strategy = StateEnhancedStrategy(
            enhanced_config,
            clusterer=fitted_clusterer,
            pattern_matcher=fitted_matcher,
        )

        signals = strategy.generate_signals(
            features,
            datetime(2024, 1, 1, 10, 30),
            state=sample_states[0],
        )

        assert len(signals) == 1
        # Should have regime info
        assert signals[0].metadata.regime_label is not None
        # Should have pattern info
        assert signals[0].metadata.pattern_match_count > 0
        # Should have size
        assert signals[0].size > 0

    def test_generate_signals_flat(
        self,
        enhanced_config,
        fitted_clusterer,
        fitted_matcher,
        sample_features,
        sample_states,
    ):
        """Test generating flat signals."""
        # Set neutral momentum
        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = 0.0

        strategy = StateEnhancedStrategy(
            enhanced_config,
            clusterer=fitted_clusterer,
            pattern_matcher=fitted_matcher,
        )

        signals = strategy.generate_signals(
            features,
            datetime(2024, 1, 1, 10, 30),
            state=sample_states[0],
        )

        assert len(signals) == 1
        assert signals[0].direction == SignalDirection.FLAT

    def test_regime_filter_blocks_signal(
        self, fitted_clusterer, fitted_matcher, sample_features, sample_states
    ):
        """Test that regime filter can block signals."""
        # High min_sharpe to force blocking
        config = StateEnhancedConfig(
            momentum_config=MomentumConfig(
                symbols=["AAPL"],
                long_threshold=0.001,
            ),
            regime_filter_config=RegimeFilterConfig(min_sharpe=100.0),
            pattern_match_config=PatternMatchConfig(k_neighbors=5, backend="sklearn"),
            enable_regime_filter=True,
            enable_pattern_matching=True,
        )

        strategy = StateEnhancedStrategy(
            config,
            clusterer=fitted_clusterer,
            pattern_matcher=fitted_matcher,
        )

        # Set high momentum
        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = 0.005

        signals = strategy.generate_signals(
            features,
            datetime(2024, 1, 1, 10, 30),
            state=sample_states[0],
        )

        # Should be blocked
        assert signals[0].direction == SignalDirection.FLAT

    def test_pattern_matching_adjusts_strength(
        self,
        enhanced_config,
        fitted_clusterer,
        sample_features,
        sample_states,
        sample_returns,
    ):
        """Test that pattern matching adjusts signal strength."""
        # Create matcher with predictable returns
        positive_returns = np.ones(100) * 0.01  # All positive
        matcher = PatternMatcher(PatternMatchConfig(k_neighbors=5, backend="sklearn"))
        matcher.fit(sample_states, positive_returns)

        strategy = StateEnhancedStrategy(
            enhanced_config,
            clusterer=fitted_clusterer,
            pattern_matcher=matcher,
        )

        # Set long signal
        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = 0.005

        signals = strategy.generate_signals(
            features,
            datetime(2024, 1, 1, 10, 30),
            state=sample_states[0],
        )

        # With all positive historical returns, long signal should be boosted
        assert signals[0].direction == SignalDirection.LONG

    def test_update_and_reset(
        self,
        enhanced_config,
        fitted_clusterer,
        fitted_matcher,
        sample_features,
    ):
        """Test update and reset methods."""
        strategy = StateEnhancedStrategy(
            enhanced_config,
            clusterer=fitted_clusterer,
            pattern_matcher=fitted_matcher,
        )

        strategy.update(sample_features)
        assert strategy.is_initialized

        strategy.reset()
        assert not strategy.is_initialized

    def test_log_decisions(
        self,
        fitted_clusterer,
        fitted_matcher,
        sample_features,
        sample_states,
    ):
        """Test decision logging."""
        config = StateEnhancedConfig(
            momentum_config=MomentumConfig(symbols=["AAPL"]),
            regime_filter_config=RegimeFilterConfig(min_sharpe=-10.0),
            pattern_match_config=PatternMatchConfig(k_neighbors=5, backend="sklearn"),
            log_decisions=True,
        )

        strategy = StateEnhancedStrategy(
            config,
            clusterer=fitted_clusterer,
            pattern_matcher=fitted_matcher,
        )

        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = 0.005

        strategy.generate_signals(
            features,
            datetime(2024, 1, 1, 10, 30),
            state=sample_states[0],
        )

        assert len(strategy.decisions) == 1
        assert "regime_label" in strategy.decisions[0]
        assert "pattern_match_count" in strategy.decisions[0]

    def test_enhancement_stats(
        self,
        enhanced_config,
        fitted_clusterer,
        fitted_matcher,
        sample_features,
        sample_states,
    ):
        """Test enhancement statistics."""
        strategy = StateEnhancedStrategy(
            StateEnhancedConfig(
                momentum_config=MomentumConfig(symbols=["AAPL"]),
                regime_filter_config=RegimeFilterConfig(min_sharpe=-10.0),
                pattern_match_config=PatternMatchConfig(k_neighbors=5, backend="sklearn"),
                log_decisions=True,
            ),
            clusterer=fitted_clusterer,
            pattern_matcher=fitted_matcher,
        )

        # Generate several signals
        for i in range(10):
            features = sample_features.copy()
            features.loc[features.index[-1], "r5"] = 0.005 * (1 if i % 2 == 0 else -1)

            strategy.generate_signals(
                features,
                datetime(2024, 1, 1, 10, 30),
                state=sample_states[i],
            )

        stats = strategy.get_enhancement_stats()
        assert stats["total_signals"] == 10
        assert "regime_filter_rate" in stats
        assert "pattern_boost_rate" in stats

    def test_set_regime_filter(self, enhanced_config, fitted_matcher, sample_states, sample_returns):
        """Test updating regime filter."""
        config = StateEnhancedConfig(
            enable_regime_filter=False,
            enable_pattern_matching=True,
            pattern_match_config=PatternMatchConfig(k_neighbors=5, backend="sklearn"),
        )
        strategy = StateEnhancedStrategy(config, pattern_matcher=fitted_matcher)

        assert strategy.regime_filter is None

        # Add regime filter later
        clusterer = RegimeClusterer(n_clusters=3, random_state=42)
        clusterer.fit(sample_states, sample_returns)
        strategy.set_regime_filter(clusterer)

        assert strategy.regime_filter is not None

    def test_set_pattern_matcher(self, enhanced_config, fitted_clusterer, sample_states, sample_returns):
        """Test updating pattern matcher."""
        config = StateEnhancedConfig(
            enable_regime_filter=True,
            enable_pattern_matching=False,
            regime_filter_config=RegimeFilterConfig(min_sharpe=-10.0),
        )
        strategy = StateEnhancedStrategy(config, clusterer=fitted_clusterer)

        assert strategy.pattern_matcher is None

        # Add pattern matcher later
        matcher = PatternMatcher(PatternMatchConfig(k_neighbors=5, backend="sklearn"))
        matcher.fit(sample_states, sample_returns)
        strategy.set_pattern_matcher(matcher)

        assert strategy.pattern_matcher is not None

    def test_batch_processing(
        self,
        enhanced_config,
        fitted_clusterer,
        fitted_matcher,
        sample_features,
        sample_states,
    ):
        """Test batch signal processing."""
        enhanced_config.momentum_config.symbols = ["AAPL", "MSFT", "GOOG"]

        strategy = StateEnhancedStrategy(
            enhanced_config,
            clusterer=fitted_clusterer,
            pattern_matcher=fitted_matcher,
        )

        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = 0.005

        signals = strategy.generate_signals(
            features,
            datetime(2024, 1, 1, 10, 30),
            states=sample_states[:3],
        )

        assert len(signals) == 3
