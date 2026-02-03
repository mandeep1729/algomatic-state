"""Trading Buddy - Trade evaluation and decision support platform.

A trading copilot that improves trading decisions by surfacing risk,
context, and inconsistencies - without predicting prices or generating signals.

Core Modules:
- domain: Core domain objects (TradeIntent, EvaluationResult, Evidence)
- context: Market context infrastructure (ContextPack, ContextPackBuilder)
- evaluators: Evaluation framework and implementations
- orchestrator: Evaluation coordination
- guardrails: Non-predictive output validation

Supporting Modules:
- data: Database models and data access
- features: Feature engineering and state detection
- backtest: Backtesting infrastructure
- execution: Order execution
"""

from src.trade.intent import (
    TradeDirection,
    TradeIntentStatus,
    TradeIntent,
)
from src.trade.evaluation import (
    Severity,
    Evidence,
    EvaluationItem,
    EvaluationResult,
)
from src.evaluators.context import (
    ContextPack,
    ContextPackBuilder,
    RegimeContext,
    KeyLevels,
    get_context_builder,
)
from src.orchestrator import (
    EvaluatorOrchestrator,
    OrchestratorConfig,
    evaluate_trade,
)
from src.data.database.trading_repository import TradingBuddyRepository
from src.rules.guardrails import (
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
