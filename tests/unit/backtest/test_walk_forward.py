"""Tests for walk-forward validation."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.backtest.walk_forward import (
    WalkForwardValidator,
    WalkForwardConfig,
    WalkForwardWindow,
    WalkForwardResult,
)
from src.strategy.base import BaseStrategy
from src.strategy.signals import Signal, SignalDirection


class SimpleStrategy(BaseStrategy):
    """Simple strategy for testing."""

    @property
    def required_features(self):
        return []

    def generate_signals(self, features, timestamp, **kwargs):
        # Random signal based on timestamp
        if timestamp.minute % 30 == 0:
            return [Signal(
                timestamp=timestamp,
                symbol="default",
                direction=SignalDirection.LONG,
                strength=0.5,
                size=5000,
            )]
        return []


@pytest.fixture
def long_ohlcv_data() -> dict[str, pd.DataFrame]:
    """Create longer OHLCV data for walk-forward testing."""
    np.random.seed(42)
    # 1 year of daily data
    n_days = 365
    n_bars_per_day = 390
    n_bars = n_days * n_bars_per_day

    # Create minute-level data
    dates = []
    current = datetime(2024, 1, 1, 9, 30)
    for day in range(n_days):
        for minute in range(n_bars_per_day):
            dates.append(current + timedelta(days=day, minutes=minute))

    # Subsample to make test faster
    dates = dates[::100]  # Every 100th bar
    n_bars = len(dates)

    index = pd.DatetimeIndex(dates)

    # Generate prices
    base_price = 100.0
    returns = np.random.randn(n_bars) * 0.002
    prices = base_price * np.exp(np.cumsum(returns))

    df = pd.DataFrame({
        "open": prices,
        "high": prices * 1.002,
        "low": prices * 0.998,
        "close": prices,
        "volume": np.random.randint(1000, 10000, n_bars),
    }, index=index)

    return {"AAPL": df}


class TestWalkForwardConfig:
    """Tests for WalkForwardConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = WalkForwardConfig()
        assert config.train_period_days == 180
        assert config.test_period_days == 30
        assert config.step_days == 30

    def test_custom_config(self):
        """Test custom configuration."""
        config = WalkForwardConfig(
            train_period_days=90,
            test_period_days=15,
        )
        assert config.train_period_days == 90
        assert config.test_period_days == 15


class TestWalkForwardWindow:
    """Tests for WalkForwardWindow."""

    def test_window_creation(self):
        """Test window creation."""
        window = WalkForwardWindow(
            window_id=0,
            train_start=datetime(2024, 1, 1),
            train_end=datetime(2024, 4, 1),
            test_start=datetime(2024, 4, 1),
            test_end=datetime(2024, 5, 1),
        )
        assert window.window_id == 0
        assert window.train_result is None
        assert window.test_result is None

    def test_window_to_dict(self):
        """Test window serialization."""
        window = WalkForwardWindow(
            window_id=0,
            train_start=datetime(2024, 1, 1),
            train_end=datetime(2024, 4, 1),
            test_start=datetime(2024, 4, 1),
            test_end=datetime(2024, 5, 1),
        )
        d = window.to_dict()
        assert d["window_id"] == 0
        assert "train_start" in d
        assert "test_start" in d


class TestWalkForwardValidator:
    """Tests for WalkForwardValidator."""

    def test_init_default(self):
        """Test default initialization."""
        validator = WalkForwardValidator()
        assert validator.config.train_period_days == 180

    def test_init_custom_config(self):
        """Test custom config initialization."""
        config = WalkForwardConfig(train_period_days=90)
        validator = WalkForwardValidator(config)
        assert validator.config.train_period_days == 90

    def test_generate_windows(self, long_ohlcv_data):
        """Test window generation."""
        config = WalkForwardConfig(
            train_period_days=90,
            test_period_days=30,
            step_days=30,
        )
        validator = WalkForwardValidator(config)

        windows = validator._generate_windows(long_ohlcv_data)

        assert len(windows) > 0
        # Check window structure
        for w in windows:
            assert w.train_start < w.train_end
            assert w.train_end == w.test_start
            assert w.test_start < w.test_end

    def test_run_returns_result(self, long_ohlcv_data):
        """Test that run returns WalkForwardResult."""
        config = WalkForwardConfig(
            train_period_days=60,
            test_period_days=30,
            step_days=30,
        )
        validator = WalkForwardValidator(config)

        result = validator.run(
            long_ohlcv_data,
            strategy_factory=SimpleStrategy,
        )

        assert isinstance(result, WalkForwardResult)
        assert len(result.windows) > 0

    def test_combined_metrics_calculated(self, long_ohlcv_data):
        """Test that combined metrics are calculated."""
        config = WalkForwardConfig(
            train_period_days=60,
            test_period_days=30,
            step_days=30,
        )
        validator = WalkForwardValidator(config)

        result = validator.run(
            long_ohlcv_data,
            strategy_factory=SimpleStrategy,
        )

        assert result.combined_metrics is not None

    def test_metrics_summary_calculated(self, long_ohlcv_data):
        """Test that metrics summaries are calculated."""
        config = WalkForwardConfig(
            train_period_days=60,
            test_period_days=30,
            step_days=30,
        )
        validator = WalkForwardValidator(config)

        result = validator.run(
            long_ohlcv_data,
            strategy_factory=SimpleStrategy,
        )

        assert "n_windows" in result.train_metrics_summary
        assert "sharpe_mean" in result.train_metrics_summary
        assert "n_windows" in result.test_metrics_summary

    def test_result_to_dict(self, long_ohlcv_data):
        """Test result serialization."""
        config = WalkForwardConfig(
            train_period_days=60,
            test_period_days=30,
            step_days=30,
        )
        validator = WalkForwardValidator(config)

        result = validator.run(
            long_ohlcv_data,
            strategy_factory=SimpleStrategy,
        )

        d = result.to_dict()
        assert "n_windows" in d
        assert "combined_metrics" in d
        assert "windows" in d

    def test_insufficient_data_raises(self):
        """Test that insufficient data raises error."""
        # Very short data
        short_data = {
            "AAPL": pd.DataFrame({
                "open": [100],
                "high": [101],
                "low": [99],
                "close": [100],
                "volume": [1000],
            }, index=[datetime(2024, 1, 1)])
        }

        validator = WalkForwardValidator()

        with pytest.raises(ValueError, match="No valid windows"):
            validator.run(short_data, strategy_factory=SimpleStrategy)
