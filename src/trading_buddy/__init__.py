"""Trading Buddy - Trade evaluation and decision support platform.

This module provides infrastructure for evaluating trade intents against
market context, user rules, and risk parameters.

Phase 0 Components:
- Domain objects (TradeIntent, EvaluationResult, Evidence)
- Context infrastructure (ContextPack, ContextPackBuilder)
- Evaluator framework (Evaluator ABC, registry)
- Orchestrator (EvaluatorOrchestrator)

Phase 1 Components:
- RiskRewardEvaluator (R:R ratio, position sizing, stop vs ATR)
- ExitPlanEvaluator (exit completeness and coherence)
- TradingBuddyRepository (user config loading)
- Guardrails (non-predictive output validation)
"""

from src.trading_buddy.domain import (
    TradeDirection,
    TradeIntentStatus,
    Severity,
    TradeIntent,
    Evidence,
    EvaluationItem,
    EvaluationResult,
)
from src.trading_buddy.context import (
    ContextPack,
    ContextPackBuilder,
    RegimeContext,
    KeyLevels,
    get_context_builder,
)
from src.trading_buddy.orchestrator import (
    EvaluatorOrchestrator,
    OrchestratorConfig,
    evaluate_trade,
)
from src.trading_buddy.repository import TradingBuddyRepository
from src.trading_buddy.guardrails import (
    validate_evaluation_result,
    sanitize_evaluation_result,
    contains_prediction,
    get_warning_template,
    format_warning,
)

__all__ = [
    # Domain
    "TradeDirection",
    "TradeIntentStatus",
    "Severity",
    "TradeIntent",
    "Evidence",
    "EvaluationItem",
    "EvaluationResult",
    # Context
    "ContextPack",
    "ContextPackBuilder",
    "RegimeContext",
    "KeyLevels",
    "get_context_builder",
    # Orchestrator
    "EvaluatorOrchestrator",
    "OrchestratorConfig",
    "evaluate_trade",
    # Repository
    "TradingBuddyRepository",
    # Guardrails
    "validate_evaluation_result",
    "sanitize_evaluation_result",
    "contains_prediction",
    "get_warning_template",
    "format_warning",
]
