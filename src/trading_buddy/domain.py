"""Domain objects for the Trading Buddy platform.

Defines core data contracts for trade evaluation:
- TradeIntent: User's proposed trade with entry/exit parameters
- Evidence: Standardized data backing an evaluation finding
- EvaluationItem: Single evaluation check result
- EvaluationResult: Aggregated evaluation output
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

import numpy as np


class TradeDirection(str, Enum):
    """Direction of a trade."""

    LONG = "long"
    SHORT = "short"


class TradeIntentStatus(str, Enum):
    """Status of a trade intent in the workflow."""

    DRAFT = "draft"
    PENDING_EVALUATION = "pending_evaluation"
    EVALUATED = "evaluated"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


class Severity(str, Enum):
    """Severity level for evaluation findings.

    Severity determines how issues are displayed and whether
    they block trade execution.
    """

    INFO = "info"           # Informational, no action needed
    WARNING = "warning"     # Caution advised, review recommended
    CRITICAL = "critical"   # Significant concern, strongly reconsider
    BLOCKER = "blocker"     # Must be resolved before proceeding


# Severity priority for sorting (higher = more severe)
SEVERITY_PRIORITY = {
    Severity.INFO: 0,
    Severity.WARNING: 1,
    Severity.CRITICAL: 2,
    Severity.BLOCKER: 3,
}


@dataclass
class TradeIntent:
    """A user's proposed trade for evaluation.

    Captures all parameters needed to evaluate a trade idea
    before execution.

    Attributes:
        user_id: User who created this intent
        symbol: Ticker symbol (e.g., 'AAPL')
        direction: Trade direction (long or short)
        timeframe: Setup timeframe (e.g., '5Min', '1Hour')
        entry_price: Planned entry price
        stop_loss: Stop loss price
        profit_target: Profit target price
        position_size: Number of shares/contracts
        position_value: Total position value in dollars
        rationale: User's reasoning for the trade
        created_at: Timestamp of creation
        status: Current workflow status
        intent_id: Unique identifier (set after persistence)
        account_id: Associated user account ID
        metadata: Additional flexible data
    """

    user_id: int
    symbol: str
    direction: TradeDirection
    timeframe: str
    entry_price: float
    stop_loss: float
    profit_target: float
    position_size: Optional[float] = None
    position_value: Optional[float] = None
    rationale: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: TradeIntentStatus = TradeIntentStatus.DRAFT
    intent_id: Optional[int] = None
    account_id: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate trade intent parameters."""
        self.symbol = self.symbol.upper()

        if isinstance(self.direction, str):
            self.direction = TradeDirection(self.direction.lower())
        if isinstance(self.status, str):
            self.status = TradeIntentStatus(self.status.lower())

        # Validate price relationships
        if self.direction == TradeDirection.LONG:
            if self.stop_loss >= self.entry_price:
                raise ValueError(
                    f"Long trade: stop_loss ({self.stop_loss}) must be below "
                    f"entry_price ({self.entry_price})"
                )
            if self.profit_target <= self.entry_price:
                raise ValueError(
                    f"Long trade: profit_target ({self.profit_target}) must be above "
                    f"entry_price ({self.entry_price})"
                )
        else:  # SHORT
            if self.stop_loss <= self.entry_price:
                raise ValueError(
                    f"Short trade: stop_loss ({self.stop_loss}) must be above "
                    f"entry_price ({self.entry_price})"
                )
            if self.profit_target >= self.entry_price:
                raise ValueError(
                    f"Short trade: profit_target ({self.profit_target}) must be below "
                    f"entry_price ({self.entry_price})"
                )

    @property
    def risk_per_share(self) -> float:
        """Calculate risk per share (distance to stop loss)."""
        return abs(self.entry_price - self.stop_loss)

    @property
    def reward_per_share(self) -> float:
        """Calculate reward per share (distance to target)."""
        return abs(self.profit_target - self.entry_price)

    @property
    def risk_reward_ratio(self) -> float:
        """Calculate risk:reward ratio (higher is better)."""
        risk = self.risk_per_share
        if risk == 0:
            return float('inf')
        return self.reward_per_share / risk

    @property
    def total_risk(self) -> Optional[float]:
        """Calculate total dollar risk if position size is known."""
        if self.position_size is None:
            return None
        return self.risk_per_share * self.position_size

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "intent_id": self.intent_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "timeframe": self.timeframe,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "profit_target": self.profit_target,
            "position_size": self.position_size,
            "position_value": self.position_value,
            "rationale": self.rationale,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "risk_reward_ratio": self.risk_reward_ratio,
            "total_risk": self.total_risk,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TradeIntent":
        """Create from dictionary."""
        return cls(
            intent_id=data.get("intent_id"),
            user_id=data["user_id"],
            account_id=data.get("account_id"),
            symbol=data["symbol"],
            direction=TradeDirection(data["direction"]),
            timeframe=data["timeframe"],
            entry_price=data["entry_price"],
            stop_loss=data["stop_loss"],
            profit_target=data["profit_target"],
            position_size=data.get("position_size"),
            position_value=data.get("position_value"),
            rationale=data.get("rationale"),
            status=TradeIntentStatus(data.get("status", "draft")),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Evidence:
    """Standardized evidence backing an evaluation finding.

    Evidence provides data-driven support for evaluation findings,
    enabling transparency and auditability.

    Attributes:
        metric_name: Name of the metric being reported
        value: Current value of the metric
        threshold: Threshold value for comparison (if applicable)
        comparison: Comparison operator used
        unit: Unit of measurement
        context: Additional contextual data
    """

    metric_name: str
    value: float
    threshold: Optional[float] = None
    comparison: Optional[Literal["<", "<=", ">", ">=", "==", "!="]] = None
    unit: Optional[str] = None
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Convert numpy types to Python native types."""
        if isinstance(self.value, (np.floating, np.integer)):
            self.value = float(self.value)
        if self.threshold is not None and isinstance(self.threshold, (np.floating, np.integer)):
            self.threshold = float(self.threshold)

    @property
    def threshold_violated(self) -> Optional[bool]:
        """Check if the threshold was violated."""
        if self.threshold is None or self.comparison is None:
            return None

        comparisons = {
            "<": lambda v, t: v < t,
            "<=": lambda v, t: v <= t,
            ">": lambda v, t: v > t,
            ">=": lambda v, t: v >= t,
            "==": lambda v, t: v == t,
            "!=": lambda v, t: v != t,
        }
        return comparisons[self.comparison](self.value, self.threshold)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "metric_name": self.metric_name,
            "value": self.value,
        }
        if self.threshold is not None:
            result["threshold"] = self.threshold
        if self.comparison is not None:
            result["comparison"] = self.comparison
        if self.unit is not None:
            result["unit"] = self.unit
        if self.context:
            result["context"] = self.context
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Evidence":
        """Create from dictionary."""
        return cls(
            metric_name=data["metric_name"],
            value=data["value"],
            threshold=data.get("threshold"),
            comparison=data.get("comparison"),
            unit=data.get("unit"),
            context=data.get("context", {}),
        )


@dataclass
class EvaluationItem:
    """Single evaluation check result.

    Represents one finding from an evaluator, with severity,
    message, and supporting evidence.

    Attributes:
        evaluator: Name of the evaluator that produced this item
        code: Unique code identifying the check (e.g., 'RR001')
        severity: Severity level of the finding
        title: Short title for the finding
        message: Detailed explanation
        evidence: Supporting data for the finding
    """

    evaluator: str
    code: str
    severity: Severity
    title: str
    message: str
    evidence: list[Evidence] = field(default_factory=list)

    def __post_init__(self):
        """Ensure severity is enum."""
        if isinstance(self.severity, str):
            self.severity = Severity(self.severity.lower())

    @property
    def priority(self) -> int:
        """Return priority for sorting (higher = more important)."""
        return SEVERITY_PRIORITY[self.severity]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "evaluator": self.evaluator,
            "code": self.code,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "evidence": [e.to_dict() for e in self.evidence],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationItem":
        """Create from dictionary."""
        return cls(
            evaluator=data["evaluator"],
            code=data["code"],
            severity=Severity(data["severity"]),
            title=data["title"],
            message=data["message"],
            evidence=[Evidence.from_dict(e) for e in data.get("evidence", [])],
        )


@dataclass
class EvaluationResult:
    """Aggregated evaluation result from all evaluators.

    Contains the overall score, all findings, and a summary
    of the evaluation.

    Attributes:
        intent: The trade intent that was evaluated
        score: Overall score (0-100, higher is better)
        items: All evaluation findings
        summary: Brief summary text
        evaluated_at: Timestamp of evaluation
        evaluators_run: List of evaluators that were executed
        evaluation_id: Unique identifier (set after persistence)
    """

    intent: TradeIntent
    score: float
    items: list[EvaluationItem]
    summary: str
    evaluated_at: datetime = field(default_factory=datetime.utcnow)
    evaluators_run: list[str] = field(default_factory=list)
    evaluation_id: Optional[int] = None

    def __post_init__(self):
        """Validate score range."""
        if not 0 <= self.score <= 100:
            raise ValueError(f"Score must be between 0 and 100, got {self.score}")

    @property
    def blockers(self) -> list[EvaluationItem]:
        """Return blocker-level items."""
        return [i for i in self.items if i.severity == Severity.BLOCKER]

    @property
    def criticals(self) -> list[EvaluationItem]:
        """Return critical-level items."""
        return [i for i in self.items if i.severity == Severity.CRITICAL]

    @property
    def warnings(self) -> list[EvaluationItem]:
        """Return warning-level items."""
        return [i for i in self.items if i.severity == Severity.WARNING]

    @property
    def infos(self) -> list[EvaluationItem]:
        """Return info-level items."""
        return [i for i in self.items if i.severity == Severity.INFO]

    @property
    def has_blockers(self) -> bool:
        """Check if any blockers exist."""
        return len(self.blockers) > 0

    @property
    def top_issues(self) -> list[EvaluationItem]:
        """Return top 3 most severe issues."""
        sorted_items = sorted(self.items, key=lambda x: x.priority, reverse=True)
        return sorted_items[:3]

    @property
    def items_by_evaluator(self) -> dict[str, list[EvaluationItem]]:
        """Group items by evaluator name."""
        result: dict[str, list[EvaluationItem]] = {}
        for item in self.items:
            if item.evaluator not in result:
                result[item.evaluator] = []
            result[item.evaluator].append(item)
        return result

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "evaluation_id": self.evaluation_id,
            "intent": self.intent.to_dict(),
            "score": self.score,
            "items": [i.to_dict() for i in self.items],
            "summary": self.summary,
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluators_run": self.evaluators_run,
            "has_blockers": self.has_blockers,
            "top_issues": [i.to_dict() for i in self.top_issues],
            "counts": {
                "blockers": len(self.blockers),
                "criticals": len(self.criticals),
                "warnings": len(self.warnings),
                "infos": len(self.infos),
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluationResult":
        """Create from dictionary."""
        return cls(
            evaluation_id=data.get("evaluation_id"),
            intent=TradeIntent.from_dict(data["intent"]),
            score=data["score"],
            items=[EvaluationItem.from_dict(i) for i in data["items"]],
            summary=data["summary"],
            evaluated_at=datetime.fromisoformat(data["evaluated_at"]) if "evaluated_at" in data else datetime.utcnow(),
            evaluators_run=data.get("evaluators_run", []),
        )
