"""Tests for position sizer."""

from datetime import datetime

import pytest

from src.strategy.position_sizer import PositionSizer, PositionSizerConfig
from src.strategy.signals import Signal, SignalDirection, SignalMetadata


@pytest.fixture
def sample_long_signal():
    """Create sample long signal."""
    return Signal(
        timestamp=datetime(2024, 1, 1, 10, 30),
        symbol="AAPL",
        direction=SignalDirection.LONG,
        strength=0.8,
        metadata=SignalMetadata(
            momentum_value=0.003,
            volatility=0.01,
            regime_sharpe=1.5,
            pattern_confidence=0.6,
        ),
    )


@pytest.fixture
def sample_flat_signal():
    """Create sample flat signal."""
    return Signal(
        timestamp=datetime(2024, 1, 1, 10, 30),
        symbol="AAPL",
        direction=SignalDirection.FLAT,
        strength=0.0,
    )


class TestPositionSizerConfig:
    """Tests for PositionSizerConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = PositionSizerConfig()
        assert config.base_size == 10000.0
        assert config.max_size == 50000.0
        assert config.min_size == 1000.0
        assert config.sizing_method == "signal_scaled"

    def test_custom_config(self):
        """Test custom configuration."""
        config = PositionSizerConfig(
            base_size=20000.0,
            sizing_method="vol_targeted",
            vol_target=0.20,
        )
        assert config.base_size == 20000.0
        assert config.sizing_method == "vol_targeted"
        assert config.vol_target == 0.20


class TestPositionSizer:
    """Tests for PositionSizer."""

    def test_init_default(self):
        """Test default initialization."""
        sizer = PositionSizer()
        assert sizer.config.base_size == 10000.0

    def test_flat_signal_zero_size(self, sample_flat_signal):
        """Test flat signal returns zero size."""
        sizer = PositionSizer()
        result = sizer.size(sample_flat_signal)
        assert result.size == 0.0

    def test_fixed_sizing(self, sample_long_signal):
        """Test fixed position sizing."""
        config = PositionSizerConfig(
            sizing_method="fixed",
            base_size=15000.0,
        )
        sizer = PositionSizer(config)

        result = sizer.size(sample_long_signal)
        assert result.size == 15000.0

    def test_signal_scaled_sizing(self, sample_long_signal):
        """Test signal-scaled position sizing."""
        config = PositionSizerConfig(
            sizing_method="signal_scaled",
            base_size=10000.0,
        )
        sizer = PositionSizer(config)

        result = sizer.size(sample_long_signal)
        # Strength is 0.8, so base_size * 0.8 = 8000
        # But confidence scaling and vol scaling also apply
        assert result.size > 0
        assert result.size <= config.max_size

    def test_vol_targeted_sizing(self, sample_long_signal):
        """Test volatility-targeted position sizing."""
        config = PositionSizerConfig(
            sizing_method="vol_targeted",
            base_size=10000.0,
            vol_target=0.15,
        )
        sizer = PositionSizer(config)

        result = sizer.size(sample_long_signal, current_volatility=0.01)
        assert result.size > 0

    def test_kelly_sizing(self):
        """Test Kelly criterion sizing."""
        signal = Signal(
            timestamp=datetime(2024, 1, 1, 10, 30),
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strength=0.8,
            metadata=SignalMetadata(
                pattern_match_count=10,
                pattern_expected_return=0.005,
                pattern_confidence=0.7,
                volatility=0.01,
            ),
        )

        config = PositionSizerConfig(
            sizing_method="kelly",
            base_size=10000.0,
        )
        sizer = PositionSizer(config)

        result = sizer.size(signal)
        assert result.size >= 0
        assert result.size <= config.max_size

    def test_max_size_cap(self, sample_long_signal):
        """Test that size is capped at max_size."""
        config = PositionSizerConfig(
            sizing_method="fixed",
            base_size=100000.0,  # Very large
            max_size=50000.0,
        )
        sizer = PositionSizer(config)

        result = sizer.size(sample_long_signal)
        assert result.size == 50000.0

    def test_min_size_floor(self):
        """Test that size is floored at min_size."""
        # Very weak signal
        signal = Signal(
            timestamp=datetime(2024, 1, 1, 10, 30),
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strength=0.01,
            metadata=SignalMetadata(volatility=0.1),  # High vol
        )

        config = PositionSizerConfig(
            sizing_method="signal_scaled",
            base_size=10000.0,
            min_size=1000.0,
        )
        sizer = PositionSizer(config)

        result = sizer.size(signal)
        assert result.size >= 1000.0

    def test_confidence_scaling(self):
        """Test confidence-based scaling."""
        # High confidence signal
        high_conf = Signal(
            timestamp=datetime(2024, 1, 1, 10, 30),
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strength=0.8,
            metadata=SignalMetadata(
                regime_sharpe=2.0,
                pattern_confidence=0.9,
                volatility=0.01,
            ),
        )

        # Low confidence signal
        low_conf = Signal(
            timestamp=datetime(2024, 1, 1, 10, 30),
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strength=0.8,
            metadata=SignalMetadata(
                regime_sharpe=0.0,
                pattern_confidence=0.1,
                volatility=0.01,
            ),
        )

        config = PositionSizerConfig(
            sizing_method="signal_scaled",
            regime_scale=1.0,
            pattern_scale=1.0,
        )
        sizer = PositionSizer(config)

        high_result = sizer.size(high_conf)
        low_result = sizer.size(low_conf)

        # High confidence should have larger size
        assert high_result.size >= low_result.size

    def test_size_batch(self, sample_long_signal, sample_flat_signal):
        """Test batch sizing."""
        sizer = PositionSizer()

        signals = [sample_long_signal, sample_flat_signal]
        results = sizer.size_batch(signals)

        assert len(results) == 2
        assert results[0].size > 0
        assert results[1].size == 0

    def test_size_batch_with_volatilities(self, sample_long_signal):
        """Test batch sizing with volatilities."""
        sizer = PositionSizer()

        signals = [sample_long_signal, sample_long_signal]
        vols = [0.01, 0.05]  # Different volatilities

        results = sizer.size_batch(signals, vols)
        assert len(results) == 2
        # Higher vol should result in smaller position (for non-fixed methods)

    def test_portfolio_allocation(self, sample_long_signal):
        """Test portfolio allocation across multiple signals."""
        sizer = PositionSizer(PositionSizerConfig(base_size=50000.0))

        signals = [sample_long_signal] * 5
        total_capital = 100000.0

        allocated = sizer.calculate_portfolio_allocation(
            signals,
            total_capital=total_capital,
            max_position_pct=0.1,
        )

        # Total allocation should not exceed capital
        total_allocated = sum(s.size for s in allocated)
        assert total_allocated <= total_capital

        # No single position should exceed 10%
        for s in allocated:
            assert s.size <= total_capital * 0.1
