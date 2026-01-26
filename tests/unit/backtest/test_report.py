"""Tests for performance reporting."""

from datetime import datetime
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.backtest.engine import BacktestConfig, BacktestResult, Trade, SignalDirection
from src.backtest.metrics import PerformanceMetrics
from src.backtest.report import PerformanceReport, ReportConfig


@pytest.fixture
def sample_result(sample_equity_curve, sample_trades) -> BacktestResult:
    """Create sample backtest result."""
    # Convert sample_trades dicts to Trade objects
    trades = [
        Trade(
            symbol=t["symbol"],
            direction=SignalDirection(t["direction"]),
            quantity=t["quantity"],
            entry_price=t["entry_price"],
            exit_price=t["exit_price"],
            entry_time=t["entry_time"],
            exit_time=t["exit_time"],
            pnl=t["pnl"],
            commission=t["commission"],
            slippage=t["slippage"],
        )
        for t in sample_trades
    ]

    return BacktestResult(
        equity_curve=sample_equity_curve,
        positions_history=[],
        trades=trades,
        signals=[],
        metrics=PerformanceMetrics(
            total_return=0.15,
            annualized_return=0.18,
            sharpe_ratio=1.5,
            sortino_ratio=2.0,
            max_drawdown=0.08,
            calmar_ratio=2.25,
            total_trades=3,
            winning_trades=2,
            losing_trades=1,
            win_rate=0.67,
            profit_factor=2.3,
        ),
        config=BacktestConfig(),
    )


class TestReportConfig:
    """Tests for ReportConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = ReportConfig()
        assert config.include_equity_curve is True
        assert config.include_drawdown is True
        assert config.output_format == "dict"

    def test_custom_config(self):
        """Test custom configuration."""
        config = ReportConfig(
            title="Custom Report",
            include_monthly_heatmap=False,
        )
        assert config.title == "Custom Report"
        assert config.include_monthly_heatmap is False


class TestPerformanceReport:
    """Tests for PerformanceReport."""

    def test_init_default(self):
        """Test default initialization."""
        report = PerformanceReport()
        assert report.config.include_equity_curve is True

    def test_generate_returns_dict(self, sample_result):
        """Test that generate returns dictionary."""
        report = PerformanceReport()
        output = report.generate(sample_result)

        assert isinstance(output, dict)
        assert "title" in output
        assert "summary" in output
        assert "metrics" in output

    def test_summary_contains_key_metrics(self, sample_result):
        """Test that summary contains key metrics."""
        report = PerformanceReport()
        output = report.generate(sample_result)

        summary = output["summary"]
        assert "total_return_pct" in summary
        assert "sharpe_ratio" in summary
        assert "max_drawdown_pct" in summary
        assert "win_rate_pct" in summary

    def test_equity_curve_included(self, sample_result):
        """Test that equity curve data is included."""
        config = ReportConfig(include_equity_curve=True)
        report = PerformanceReport(config)
        output = report.generate(sample_result)

        assert "equity_curve" in output
        assert "timestamps" in output["equity_curve"]
        assert "values" in output["equity_curve"]

    def test_equity_curve_excluded(self, sample_result):
        """Test that equity curve can be excluded."""
        config = ReportConfig(include_equity_curve=False)
        report = PerformanceReport(config)
        output = report.generate(sample_result)

        assert "equity_curve" not in output

    def test_drawdown_included(self, sample_result):
        """Test that drawdown data is included."""
        config = ReportConfig(include_drawdown=True)
        report = PerformanceReport(config)
        output = report.generate(sample_result)

        assert "drawdown" in output
        assert "max_drawdown_pct" in output["drawdown"]

    def test_trade_analysis_included(self, sample_result):
        """Test that trade analysis is included."""
        config = ReportConfig(include_trade_analysis=True)
        report = PerformanceReport(config)
        output = report.generate(sample_result)

        assert "trade_analysis" in output
        assert "total_trades" in output["trade_analysis"]
        assert "by_direction" in output["trade_analysis"]

    def test_to_markdown(self, sample_result):
        """Test markdown conversion."""
        report = PerformanceReport()
        output = report.generate(sample_result)
        md = report.to_markdown(output)

        assert isinstance(md, str)
        assert "# " in md  # Has heading
        assert "Sharpe Ratio" in md
        assert "%" in md  # Has percentage values

    def test_save_json(self, sample_result):
        """Test saving as JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"

            report = PerformanceReport()
            output = report.generate(sample_result)
            report.save(output, path)

            assert path.exists()
            content = path.read_text()
            assert "total_return" in content

    def test_save_markdown(self, sample_result):
        """Test saving as markdown."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.md"

            config = ReportConfig(output_format="markdown")
            report = PerformanceReport(config)
            output = report.generate(sample_result)
            report.save(output, path)

            assert path.exists()
            content = path.read_text()
            assert "# " in content

    def test_empty_trades_handled(self, sample_equity_curve):
        """Test that empty trades are handled."""
        result = BacktestResult(
            equity_curve=sample_equity_curve,
            positions_history=[],
            trades=[],
            signals=[],
            metrics=PerformanceMetrics(),
            config=BacktestConfig(),
        )

        report = PerformanceReport()
        output = report.generate(result)

        assert output["trade_analysis"]["total_trades"] == 0

    def test_pnl_distribution_stats(self, sample_result):
        """Test PnL distribution statistics."""
        report = PerformanceReport()
        output = report.generate(sample_result)

        analysis = output["trade_analysis"]
        assert "pnl_distribution" in analysis
        pnl = analysis["pnl_distribution"]
        assert "mean" in pnl
        assert "std" in pnl
        assert "median" in pnl

    def test_duration_distribution_stats(self, sample_result):
        """Test trade duration statistics."""
        report = PerformanceReport()
        output = report.generate(sample_result)

        analysis = output["trade_analysis"]
        assert "duration_distribution" in analysis
        duration = analysis["duration_distribution"]
        assert "mean_minutes" in duration
