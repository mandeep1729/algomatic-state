"""Evaluator framework for Trading Buddy.

Provides base classes, registry, and utilities for building
trade evaluation modules.
"""

from src.evaluators.base import Evaluator, EvaluatorConfig
from src.evaluators.registry import (
    register_evaluator,
    get_evaluator,
    get_all_evaluators,
    list_evaluators,
)
from src.evaluators.evidence import (
    check_threshold,
    compute_zscore,
    compare_to_atr,
    format_percentage,
    format_currency,
    format_ratio,
)

# Import evaluators to trigger registration
from src.evaluators.risk_reward import RiskRewardEvaluator
from src.evaluators.exit_plan import ExitPlanEvaluator
from src.evaluators.regime_fit import RegimeFitEvaluator
from src.evaluators.mtfa import MTFAEvaluator

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
    # Evaluators
    "RiskRewardEvaluator",
    "ExitPlanEvaluator",
    "RegimeFitEvaluator",
    "MTFAEvaluator",
]
