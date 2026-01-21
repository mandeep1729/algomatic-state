"""Tests for momentum strategy."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src.strategy.momentum import MomentumStrategy, MomentumConfig
from src.strategy.signals import SignalDirection


class TestMomentumConfig:
    """Tests for MomentumConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MomentumConfig()
        assert config.name == "momentum"
        assert config.momentum_feature == "r5"
        assert config.long_threshold == 0.001
        assert config.short_threshold == -0.001
        assert config.signal_mode == "both"

    def test_custom_config(self):
        """Test custom configuration."""
        config = MomentumConfig(
            momentum_feature="r15",
            long_threshold=0.002,
            short_threshold=-0.002,
            signal_mode="long_only",
        )
        assert config.momentum_feature == "r15"
        assert config.long_threshold == 0.002
        assert config.signal_mode == "long_only"


class TestMomentumStrategy:
    """Tests for MomentumStrategy."""

    def test_init_default(self):
        """Test default initialization."""
        strategy = MomentumStrategy()
        assert strategy.name == "momentum"
        assert not strategy.is_initialized

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = MomentumConfig(long_threshold=0.005)
        strategy = MomentumStrategy(config)
        assert strategy.config.long_threshold == 0.005

    def test_required_features(self):
        """Test required features property."""
        strategy = MomentumStrategy()
        assert "r5" in strategy.required_features

        config = MomentumConfig(momentum_feature="r15")
        strategy = MomentumStrategy(config)
        assert "r15" in strategy.required_features

    def test_generate_long_signal(self, sample_features, sample_timestamp):
        """Test generating a long signal."""
        # Set high positive momentum
        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = 0.005

        config = MomentumConfig(
            long_threshold=0.001,
            symbols=["AAPL"],
        )
        strategy = MomentumStrategy(config)

        signals = strategy.generate_signals(features, sample_timestamp)
        assert len(signals) == 1
        assert signals[0].direction == SignalDirection.LONG
        assert signals[0].symbol == "AAPL"
        assert signals[0].metadata.momentum_value == 0.005

    def test_generate_short_signal(self, sample_features, sample_timestamp):
        """Test generating a short signal."""
        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = -0.005

        config = MomentumConfig(
            short_threshold=-0.001,
            symbols=["AAPL"],
        )
        strategy = MomentumStrategy(config)

        signals = strategy.generate_signals(features, sample_timestamp)
        assert len(signals) == 1
        assert signals[0].direction == SignalDirection.SHORT

    def test_generate_flat_signal(self, sample_features, sample_timestamp):
        """Test generating a flat signal."""
        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = 0.0005  # Below threshold

        config = MomentumConfig(
            long_threshold=0.001,
            short_threshold=-0.001,
            symbols=["AAPL"],
        )
        strategy = MomentumStrategy(config)

        signals = strategy.generate_signals(features, sample_timestamp)
        assert len(signals) == 1
        assert signals[0].direction == SignalDirection.FLAT

    def test_long_only_mode(self, sample_features, sample_timestamp):
        """Test long-only signal mode."""
        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = -0.005  # Strong negative

        config = MomentumConfig(
            signal_mode="long_only",
            symbols=["AAPL"],
        )
        strategy = MomentumStrategy(config)

        signals = strategy.generate_signals(features, sample_timestamp)
        # Should be flat, not short
        assert signals[0].direction == SignalDirection.FLAT

    def test_short_only_mode(self, sample_features, sample_timestamp):
        """Test short-only signal mode."""
        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = 0.005  # Strong positive

        config = MomentumConfig(
            signal_mode="short_only",
            symbols=["AAPL"],
        )
        strategy = MomentumStrategy(config)

        signals = strategy.generate_signals(features, sample_timestamp)
        # Should be flat, not long
        assert signals[0].direction == SignalDirection.FLAT

    def test_signal_strength_linear(self, sample_features, sample_timestamp):
        """Test linear signal strength scaling."""
        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = 0.002  # 2x threshold

        config = MomentumConfig(
            long_threshold=0.001,
            strength_scaling="linear",
            symbols=["AAPL"],
        )
        strategy = MomentumStrategy(config)

        signals = strategy.generate_signals(features, sample_timestamp)
        # Excess is (0.002 - 0.001) / 0.001 = 1.0
        assert signals[0].strength == 1.0

    def test_signal_strength_binary(self, sample_features, sample_timestamp):
        """Test binary signal strength."""
        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = 0.0015  # Just above threshold

        config = MomentumConfig(
            long_threshold=0.001,
            strength_scaling="binary",
            symbols=["AAPL"],
        )
        strategy = MomentumStrategy(config)

        signals = strategy.generate_signals(features, sample_timestamp)
        assert signals[0].strength == 1.0

    def test_missing_feature_raises(self, sample_timestamp):
        """Test that missing feature raises error."""
        features = pd.DataFrame({"other_feature": [1, 2, 3]})

        strategy = MomentumStrategy()
        with pytest.raises(ValueError, match="Required feature"):
            strategy.generate_signals(features, sample_timestamp)

    def test_update_tracks_history(self, sample_features):
        """Test that update tracks momentum history."""
        config = MomentumConfig(symbols=["AAPL"])
        strategy = MomentumStrategy(config)

        strategy.update(sample_features)
        assert strategy.is_initialized

        stats = strategy.get_momentum_stats("AAPL")
        assert "mean" in stats
        assert "std" in stats

    def test_reset_clears_state(self, sample_features):
        """Test that reset clears strategy state."""
        config = MomentumConfig(symbols=["AAPL"])
        strategy = MomentumStrategy(config)

        strategy.update(sample_features)
        assert strategy.is_initialized

        strategy.reset()
        assert not strategy.is_initialized
        assert strategy.get_momentum_stats("AAPL")["mean"] == 0.0

    def test_nan_momentum_returns_flat(self, sample_features, sample_timestamp):
        """Test that NaN momentum returns flat signal."""
        features = sample_features.copy()
        features.loc[features.index[-1], "r5"] = np.nan

        config = MomentumConfig(symbols=["AAPL"])
        strategy = MomentumStrategy(config)

        signals = strategy.generate_signals(features, sample_timestamp)
        assert signals[0].direction == SignalDirection.FLAT
