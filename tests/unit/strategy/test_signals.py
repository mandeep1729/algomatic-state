"""Tests for signal types."""

from datetime import datetime

import pytest

from src.strategy.signals import Signal, SignalDirection, SignalMetadata


class TestSignalDirection:
    """Tests for SignalDirection enum."""

    def test_direction_values(self):
        """Test direction enum values."""
        assert SignalDirection.LONG.value == "long"
        assert SignalDirection.SHORT.value == "short"
        assert SignalDirection.FLAT.value == "flat"

    def test_direction_str(self):
        """Test direction string representation."""
        assert str(SignalDirection.LONG) == "long"
        assert str(SignalDirection.SHORT) == "short"
        assert str(SignalDirection.FLAT) == "flat"


class TestSignalMetadata:
    """Tests for SignalMetadata dataclass."""

    def test_default_values(self):
        """Test default metadata values."""
        meta = SignalMetadata()
        assert meta.regime_label is None
        assert meta.regime_sharpe is None
        assert meta.pattern_match_count == 0
        assert meta.pattern_expected_return == 0.0
        assert meta.pattern_confidence == 0.0
        assert meta.momentum_value == 0.0
        assert meta.volatility == 0.0
        assert meta.custom == {}

    def test_custom_values(self):
        """Test metadata with custom values."""
        meta = SignalMetadata(
            regime_label=2,
            regime_sharpe=1.5,
            momentum_value=0.003,
            custom={"extra": "data"},
        )
        assert meta.regime_label == 2
        assert meta.regime_sharpe == 1.5
        assert meta.momentum_value == 0.003
        assert meta.custom == {"extra": "data"}


class TestSignal:
    """Tests for Signal dataclass."""

    def test_create_signal(self, sample_timestamp):
        """Test basic signal creation."""
        signal = Signal(
            timestamp=sample_timestamp,
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strength=0.8,
        )
        assert signal.timestamp == sample_timestamp
        assert signal.symbol == "AAPL"
        assert signal.direction == SignalDirection.LONG
        assert signal.strength == 0.8
        assert signal.size == 0.0

    def test_signal_validation_strength(self, sample_timestamp):
        """Test signal strength validation."""
        with pytest.raises(ValueError, match="strength must be between"):
            Signal(
                timestamp=sample_timestamp,
                symbol="AAPL",
                direction=SignalDirection.LONG,
                strength=1.5,
            )

        with pytest.raises(ValueError, match="strength must be between"):
            Signal(
                timestamp=sample_timestamp,
                symbol="AAPL",
                direction=SignalDirection.LONG,
                strength=-0.1,
            )

    def test_signal_validation_size(self, sample_timestamp):
        """Test signal size validation."""
        with pytest.raises(ValueError, match="size must be non-negative"):
            Signal(
                timestamp=sample_timestamp,
                symbol="AAPL",
                direction=SignalDirection.LONG,
                size=-100,
            )

    def test_signal_properties(self, sample_timestamp):
        """Test signal property methods."""
        long_signal = Signal(
            timestamp=sample_timestamp,
            symbol="AAPL",
            direction=SignalDirection.LONG,
        )
        assert long_signal.is_long
        assert not long_signal.is_short
        assert long_signal.is_entry
        assert not long_signal.is_exit

        short_signal = Signal(
            timestamp=sample_timestamp,
            symbol="AAPL",
            direction=SignalDirection.SHORT,
        )
        assert not short_signal.is_long
        assert short_signal.is_short
        assert short_signal.is_entry
        assert not short_signal.is_exit

        flat_signal = Signal(
            timestamp=sample_timestamp,
            symbol="AAPL",
            direction=SignalDirection.FLAT,
        )
        assert not flat_signal.is_long
        assert not flat_signal.is_short
        assert not flat_signal.is_entry
        assert flat_signal.is_exit

    def test_with_size(self, sample_timestamp):
        """Test creating signal copy with new size."""
        signal = Signal(
            timestamp=sample_timestamp,
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strength=0.8,
        )
        sized_signal = signal.with_size(10000.0)
        assert sized_signal.size == 10000.0
        assert sized_signal.strength == 0.8
        assert signal.size == 0.0  # Original unchanged

    def test_with_strength(self, sample_timestamp):
        """Test creating signal copy with new strength."""
        signal = Signal(
            timestamp=sample_timestamp,
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strength=0.8,
        )
        modified = signal.with_strength(0.5)
        assert modified.strength == 0.5
        assert signal.strength == 0.8  # Original unchanged

    def test_to_dict(self, sample_timestamp):
        """Test signal serialization to dict."""
        signal = Signal(
            timestamp=sample_timestamp,
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strength=0.8,
            size=10000.0,
            metadata=SignalMetadata(regime_label=2, momentum_value=0.003),
        )
        data = signal.to_dict()
        assert data["symbol"] == "AAPL"
        assert data["direction"] == "long"
        assert data["strength"] == 0.8
        assert data["size"] == 10000.0
        assert data["metadata"]["regime_label"] == 2

    def test_from_dict(self, sample_timestamp):
        """Test signal deserialization from dict."""
        data = {
            "timestamp": sample_timestamp.isoformat(),
            "symbol": "AAPL",
            "direction": "long",
            "strength": 0.8,
            "size": 10000.0,
            "metadata": {
                "regime_label": 2,
                "momentum_value": 0.003,
            },
        }
        signal = Signal.from_dict(data)
        assert signal.symbol == "AAPL"
        assert signal.direction == SignalDirection.LONG
        assert signal.strength == 0.8
        assert signal.metadata.regime_label == 2
