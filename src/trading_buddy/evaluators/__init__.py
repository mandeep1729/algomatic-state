"""Evaluator framework for Trading Buddy.

Provides base classes, registry, and utilities for building
trade evaluation modules.
"""

from src.trading_buddy.evaluators.base import Evaluator, EvaluatorConfig
from src.trading_buddy.evaluators.registry import (
    register_evaluator,
    get_evaluator,
    get_all_evaluators,
    list_evaluators,
)
from src.trading_buddy.evaluators.evidence import (
    check_threshold,
    compute_zscore,
    compare_to_atr,
    format_percentage,
    format_currency,
    format_ratio,
)

__all__ = [
    # Base
    "Evaluator",
    "EvaluatorConfig",
    # Registry
    "register_evaluator",
    "get_evaluator",
    "get_all_evaluators",
    "list_evaluators",
    # Evidence utilities
    "check_threshold",
    "compute_zscore",
    "compare_to_atr",
    "format_percentage",
    "format_currency",
    "format_ratio",
]
