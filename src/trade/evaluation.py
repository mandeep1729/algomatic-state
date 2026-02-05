"""Trade evaluation domain objects.

Defines data contracts for evaluation results and findings.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

import numpy as np

from src.trade.intent import TradeIntent

logger = logging.getLogger(__name__)


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
            logger.error("Invalid evaluation score: %.2f (must be 0-100)", self.score)
            raise ValueError(f"Score must be between 0 and 100, got {self.score}")
        logger.debug(
            "EvaluationResult created: symbol=%s, score=%.1f, items=%d, blockers=%d",
            self.intent.symbol, self.score, len(self.items), len(self.blockers)
        )

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
