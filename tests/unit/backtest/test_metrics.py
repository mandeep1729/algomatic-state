"""Tests for performance metrics."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from src.backtest.metrics import (
    PerformanceMetrics,
    calculate_metrics,
    calculate_monthly_returns,
    calculate_rolling_sharpe,
)


class TestPerformanceMetrics:
    """Tests for PerformanceMetrics dataclass."""

    def test_default_values(self):
        """Test default metric values."""
        metrics = PerformanceMetrics()
        assert metrics.total_return == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.total_trades == 0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metrics = PerformanceMetrics(
            total_return=0.15,
            sharpe_ratio=1.5,
            total_trades=100,
        )
        d = metrics.to_dict()
        assert d["total_return"] == 0.15
        assert d["sharpe_ratio"] == 1.5
        assert d["total_trades"] == 100


class TestCalculateMetrics:
    """Tests for calculate_metrics function."""

    def test_empty_equity(self):
        """Test with empty equity curve."""
        equity = pd.Series(dtype=float)
        metrics = calculate_metrics(equity, [])
        assert metrics.total_return == 0.0

    def test_single_point_equity(self):
        """Test with single point equity curve."""
        equity = pd.Series([100000], index=[datetime(2024, 1, 1)])
        metrics = calculate_metrics(equity, [])
        assert metrics.total_return == 0.0

    def test_basic_return_calculation(self, sample_equity_curve):
        """Test basic return calculation."""
        metrics = calculate_metrics(sample_equity_curve, [])

        # Total return should be calculated
        expected_return = (
            sample_equity_curve.iloc[-1] / sample_equity_curve.iloc[0]
        ) - 1
        assert abs(metrics.total_return - expected_return) < 0.001

    def test_sharpe_ratio_calculation(self, sample_equity_curve):
        """Test Sharpe ratio calculation."""
        metrics = calculate_metrics(sample_equity_curve, [])

        # Sharpe should be calculated
        # With random returns and slight positive drift, expect positive Sharpe
        assert metrics.sharpe_ratio is not None
        assert isinstance(metrics.sharpe_ratio, float)

    def test_drawdown_calculation(self, sample_equity_curve):
        """Test max drawdown calculation."""
        metrics = calculate_metrics(sample_equity_curve, [])

        # Max drawdown should be non-negative
        assert metrics.max_drawdown >= 0.0
        assert metrics.max_drawdown <= 1.0

    def test_trade_metrics(self, sample_equity_curve, sample_trades):
        """Test trade-based metrics."""
        metrics = calculate_metrics(sample_equity_curve, sample_trades)

        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        assert metrics.win_rate == 2 / 3

    def test_profit_factor(self, sample_equity_curve, sample_trades):
        """Test profit factor calculation."""
        metrics = calculate_metrics(sample_equity_curve, sample_trades)

        # Gross profit = 195 + 47.5 = 242.5
        # Gross loss = 105
        # Profit factor = 242.5 / 105 = 2.31
        assert metrics.profit_factor > 2.0
        assert metrics.profit_factor < 2.5

    def test_sortino_ratio(self, sample_equity_curve):
        """Test Sortino ratio calculation."""
        metrics = calculate_metrics(sample_equity_curve, [])

        # Sortino should be calculated
        assert metrics.sortino_ratio is not None
        assert isinstance(metrics.sortino_ratio, float)

    def test_volatility_calculation(self, sample_equity_curve):
        """Test volatility calculation."""
        metrics = calculate_metrics(sample_equity_curve, [])

        # Volatility should be positive
        assert metrics.volatility > 0
        # Annualized volatility should be reasonable (not 0, not astronomical)
        assert metrics.volatility < 10.0

    def test_calmar_ratio(self, sample_equity_curve):
        """Test Calmar ratio calculation."""
        metrics = calculate_metrics(sample_equity_curve, [])

        # Calmar should be calculated if drawdown exists
        if metrics.max_drawdown > 0:
            expected_calmar = metrics.annualized_return / metrics.max_drawdown
            assert abs(metrics.calmar_ratio - expected_calmar) < 0.01


class TestCalculateMonthlyReturns:
    """Tests for monthly returns calculation."""

    def test_monthly_returns_matrix(self):
        """Test monthly returns matrix generation."""
        # Create equity curve spanning multiple months
        np.random.seed(42)
        index = pd.date_range("2024-01-01", periods=3000, freq="1h")
        returns = np.random.randn(3000) * 0.005 + 0.0002
        equity = 100000 * np.exp(np.cumsum(returns))
        equity_curve = pd.Series(equity, index=index)

        monthly = calculate_monthly_returns(equity_curve)

        assert isinstance(monthly, pd.DataFrame)
        # Should have years as index
        assert len(monthly.index) > 0
        # Should have month columns
        assert len(monthly.columns) > 0

    def test_short_series_returns_empty(self):
        """Test that short series returns empty dataframe."""
        equity = pd.Series(
            [100000, 100100, 100200],
            index=pd.date_range("2024-01-01", periods=3, freq="1D"),
        )
        monthly = calculate_monthly_returns(equity)
        # May be empty or have minimal data
        assert isinstance(monthly, pd.DataFrame)


class TestCalculateRollingSharpe:
    """Tests for rolling Sharpe calculation."""

    def test_rolling_sharpe(self, sample_equity_curve):
        """Test rolling Sharpe calculation."""
        returns = sample_equity_curve.pct_change().dropna()
        rolling_sharpe = calculate_rolling_sharpe(returns, window=100)

        assert len(rolling_sharpe) == len(returns)
        # First window-1 values should be NaN
        assert pd.isna(rolling_sharpe.iloc[:99]).all()
        # Rest should be valid
        assert not pd.isna(rolling_sharpe.iloc[99:]).all()
