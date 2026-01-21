"""Backtesting module for strategy evaluation.

This module provides:
- Event-driven backtesting engine
- Realistic execution simulation (slippage, commission)
- Performance metrics calculation
- Walk-forward validation
- Performance reporting
"""

from src.backtest.engine import BacktestEngine, BacktestConfig, BacktestResult
from src.backtest.metrics import PerformanceMetrics, calculate_metrics
from src.backtest.walk_forward import WalkForwardValidator, WalkForwardConfig, WalkForwardResult
from src.backtest.report import PerformanceReport, ReportConfig

__all__ = [
    # Engine
    "BacktestEngine",
    "BacktestConfig",
    "BacktestResult",
    # Metrics
    "PerformanceMetrics",
    "calculate_metrics",
    # Walk-forward
    "WalkForwardValidator",
    "WalkForwardConfig",
    "WalkForwardResult",
    # Reporting
    "PerformanceReport",
    "ReportConfig",
]
