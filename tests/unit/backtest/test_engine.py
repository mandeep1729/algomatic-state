"""Tests for backtesting engine."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import (
    BacktestEngine,
    BacktestConfig,
    BacktestResult,
    Position,
    Trade,
    BaseStrategy,
    Signal,
    SignalDirection,
)


class SimpleTestStrategy(BaseStrategy):
    """Simple strategy for testing."""

    def __init__(self, signal_direction: SignalDirection = SignalDirection.LONG):
        super().__init__()
        self._signal_direction = signal_direction
        self._signal_count = 0

    @property
    def required_features(self) -> list[str]:
        return []

    def generate_signals(self, features, timestamp, **kwargs):
        self._signal_count += 1

        # Generate signal every 100 bars
        if self._signal_count % 100 == 1:
            return [Signal(
                timestamp=timestamp,
                symbol="default",
                direction=self._signal_direction,
                strength=0.5,
                size=5000,
            )]
        elif self._signal_count % 100 == 50:
            return [Signal(
                timestamp=timestamp,
                symbol="default",
                direction=SignalDirection.FLAT,
            )]

        return []


class TestBacktestConfig:
    """Tests for BacktestConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BacktestConfig()
        assert config.initial_capital == 100000.0
        assert config.commission_per_share == 0.005
        assert config.slippage_bps == 5.0
        assert config.fill_on_next_bar is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = BacktestConfig(
            initial_capital=50000.0,
            commission_per_share=0.01,
            slippage_bps=10.0,
        )
        assert config.initial_capital == 50000.0
        assert config.commission_per_share == 0.01


class TestPosition:
    """Tests for Position dataclass."""

    def test_long_position(self):
        """Test long position properties."""
        pos = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=150.0,
            entry_time=datetime(2024, 1, 1),
        )
        assert pos.is_long
        assert not pos.is_short
        assert pos.market_value == 15000.0

    def test_short_position(self):
        """Test short position properties."""
        pos = Position(
            symbol="AAPL",
            quantity=-100,
            avg_price=150.0,
            entry_time=datetime(2024, 1, 1),
        )
        assert not pos.is_long
        assert pos.is_short
        assert pos.market_value == 15000.0

    def test_update_pnl_long(self):
        """Test P&L update for long position."""
        pos = Position(
            symbol="AAPL",
            quantity=100,
            avg_price=100.0,
            entry_time=datetime(2024, 1, 1),
        )
        pos.update_pnl(110.0)  # Price went up
        assert pos.unrealized_pnl == 1000.0  # 100 shares * $10

    def test_update_pnl_short(self):
        """Test P&L update for short position."""
        pos = Position(
            symbol="AAPL",
            quantity=-100,
            avg_price=100.0,
            entry_time=datetime(2024, 1, 1),
        )
        pos.update_pnl(90.0)  # Price went down (profit for short)
        assert pos.unrealized_pnl == 1000.0  # 100 shares * $10


class TestTrade:
    """Tests for Trade dataclass."""

    def test_trade_creation(self):
        """Test trade creation."""
        trade = Trade(
            symbol="AAPL",
            direction=SignalDirection.LONG,
            quantity=100,
            entry_price=100.0,
            exit_price=105.0,
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            pnl=500.0,
            commission=1.0,
            slippage=0.5,
        )
        assert trade.pnl == 500.0
        assert trade.commission == 1.0

    def test_trade_to_dict(self):
        """Test trade serialization."""
        trade = Trade(
            symbol="AAPL",
            direction=SignalDirection.LONG,
            quantity=100,
            entry_price=100.0,
            exit_price=105.0,
            entry_time=datetime(2024, 1, 1, 10, 0),
            exit_time=datetime(2024, 1, 1, 11, 0),
            pnl=500.0,
        )
        d = trade.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["direction"] == "long"
        assert d["pnl"] == 500.0


class TestBacktestEngine:
    """Tests for BacktestEngine."""

    def test_init_default(self):
        """Test default initialization."""
        engine = BacktestEngine()
        assert engine.config.initial_capital == 100000.0

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = BacktestConfig(initial_capital=50000.0)
        engine = BacktestEngine(config)
        assert engine.config.initial_capital == 50000.0

    def test_run_returns_result(self, sample_ohlcv_data):
        """Test that run returns BacktestResult."""
        engine = BacktestEngine()
        strategy = SimpleTestStrategy()

        result = engine.run(sample_ohlcv_data, strategy)

        assert isinstance(result, BacktestResult)
        assert len(result.equity_curve) > 0
        assert result.config is not None

    def test_equity_curve_starts_at_initial_capital(self, sample_ohlcv_data):
        """Test equity curve starts at initial capital."""
        config = BacktestConfig(initial_capital=100000.0)
        engine = BacktestEngine(config)
        strategy = SimpleTestStrategy()

        result = engine.run(sample_ohlcv_data, strategy)

        # First equity value should be initial capital
        assert result.equity_curve.iloc[0] == 100000.0

    def test_trades_are_recorded(self, sample_ohlcv_data):
        """Test that trades are recorded."""
        engine = BacktestEngine()
        strategy = SimpleTestStrategy()

        result = engine.run(sample_ohlcv_data, strategy)

        # Should have some trades
        # With 1000 bars and signals at 1, 100, 200, etc, expect multiple trades
        assert len(result.trades) > 0

    def test_commission_is_applied(self, sample_ohlcv_data):
        """Test that commission is applied to trades."""
        config = BacktestConfig(commission_per_share=0.01)
        engine = BacktestEngine(config)
        strategy = SimpleTestStrategy()

        result = engine.run(sample_ohlcv_data, strategy)

        if result.trades:
            # All trades should have commission
            for trade in result.trades:
                assert trade.commission > 0

    def test_metrics_are_calculated(self, sample_ohlcv_data):
        """Test that metrics are calculated."""
        engine = BacktestEngine()
        strategy = SimpleTestStrategy()

        result = engine.run(sample_ohlcv_data, strategy)

        assert result.metrics is not None
        assert result.metrics.total_return != 0.0 or len(result.trades) == 0

    def test_signals_are_recorded(self, sample_ohlcv_data):
        """Test that signals are recorded."""
        engine = BacktestEngine()
        strategy = SimpleTestStrategy()

        result = engine.run(sample_ohlcv_data, strategy)

        # Should have generated signals
        assert len(result.signals) > 0

    def test_result_to_dict(self, sample_ohlcv_data):
        """Test result serialization."""
        engine = BacktestEngine()
        strategy = SimpleTestStrategy()

        result = engine.run(sample_ohlcv_data, strategy)
        d = result.to_dict()

        assert "equity_curve" in d
        assert "trades" in d
        assert "metrics" in d

    def test_no_trades_when_no_signals(self, sample_ohlcv_data):
        """Test no trades when strategy generates no signals."""

        class NoSignalStrategy(BaseStrategy):
            @property
            def required_features(self):
                return []

            def generate_signals(self, features, timestamp, **kwargs):
                return []

        engine = BacktestEngine()
        strategy = NoSignalStrategy()

        result = engine.run(sample_ohlcv_data, strategy)

        assert len(result.trades) == 0

    def test_positions_history_recorded(self, sample_ohlcv_data):
        """Test that position history is recorded."""
        engine = BacktestEngine()
        strategy = SimpleTestStrategy()

        result = engine.run(sample_ohlcv_data, strategy)

        assert len(result.positions_history) > 0
        assert "timestamp" in result.positions_history[0]
        assert "equity" in result.positions_history[0]
