"""Base evaluator class and configuration.

Defines the abstract Evaluator interface that all evaluation
modules must implement.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from src.trading_buddy.domain import (
    TradeIntent,
    EvaluationItem,
    Evidence,
    Severity,
)
from src.trading_buddy.context import ContextPack

logger = logging.getLogger(__name__)


@dataclass
class EvaluatorConfig:
    """Configuration for an evaluator.

    Allows customization of evaluator behavior through
    user rules or defaults.

    Attributes:
        enabled: Whether this evaluator is active
        thresholds: Custom threshold values
        severity_overrides: Override severity for specific codes
        custom_params: Additional evaluator-specific parameters
    """

    enabled: bool = True
    thresholds: dict[str, float] = field(default_factory=dict)
    severity_overrides: dict[str, Severity] = field(default_factory=dict)
    custom_params: dict[str, Any] = field(default_factory=dict)

    def get_threshold(self, name: str, default: float) -> float:
        """Get a threshold value with fallback to default.

        Args:
            name: Threshold name
            default: Default value if not configured

        Returns:
            Threshold value
        """
        return self.thresholds.get(name, default)

    def get_severity(self, code: str, default: Severity) -> Severity:
        """Get severity for a code with fallback to default.

        Args:
            code: Evaluation code
            default: Default severity

        Returns:
            Severity level
        """
        return self.severity_overrides.get(code, default)

    def get_param(self, name: str, default: Any = None) -> Any:
        """Get a custom parameter.

        Args:
            name: Parameter name
            default: Default value

        Returns:
            Parameter value
        """
        return self.custom_params.get(name, default)

    @classmethod
    def from_dict(cls, data: dict) -> "EvaluatorConfig":
        """Create from dictionary."""
        severity_overrides = {}
        for code, sev in data.get("severity_overrides", {}).items():
            if isinstance(sev, str):
                severity_overrides[code] = Severity(sev.lower())
            else:
                severity_overrides[code] = sev

        return cls(
            enabled=data.get("enabled", True),
            thresholds=data.get("thresholds", {}),
            severity_overrides=severity_overrides,
            custom_params=data.get("custom_params", {}),
        )


class Evaluator(ABC):
    """Abstract base class for trade evaluators.

    Each evaluator examines a specific aspect of a trade intent
    (e.g., risk/reward, regime alignment, exit plan) and produces
    evaluation items with findings.

    Subclasses must implement:
    - name: Unique evaluator name
    - description: Human-readable description
    - evaluate(): Core evaluation logic

    Example:
        class RiskRewardEvaluator(Evaluator):
            name = "risk_reward"
            description = "Evaluates risk/reward ratio"

            def evaluate(self, intent, context, config):
                items = []
                if intent.risk_reward_ratio < 2.0:
                    items.append(EvaluationItem(
                        evaluator=self.name,
                        code="RR001",
                        severity=Severity.WARNING,
                        title="Low Risk/Reward",
                        message="Risk/reward ratio is below 2:1",
                        evidence=[...],
                    ))
                return items
    """

    # Must be overridden by subclasses
    name: str = "base"
    description: str = "Base evaluator"

    # Default configuration
    default_config: EvaluatorConfig = EvaluatorConfig()

    def __init__(self, config: Optional[EvaluatorConfig] = None):
        """Initialize evaluator with optional configuration.

        Args:
            config: Custom configuration (uses defaults if not provided)
        """
        self.config = config or self.default_config

    @abstractmethod
    def evaluate(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: Optional[EvaluatorConfig] = None,
    ) -> list[EvaluationItem]:
        """Evaluate a trade intent and return findings.

        Args:
            intent: The trade intent to evaluate
            context: Market context data
            config: Override configuration for this evaluation

        Returns:
            List of evaluation items (findings)
        """
        pass

    def create_item(
        self,
        code: str,
        severity: Severity,
        title: str,
        message: str,
        evidence: Optional[list[Evidence]] = None,
        config: Optional[EvaluatorConfig] = None,
    ) -> EvaluationItem:
        """Helper to create an evaluation item.

        Applies severity overrides from configuration.

        Args:
            code: Unique code for this finding
            severity: Default severity
            title: Short title
            message: Detailed message
            evidence: Supporting evidence
            config: Configuration for severity overrides

        Returns:
            EvaluationItem
        """
        cfg = config or self.config
        actual_severity = cfg.get_severity(code, severity)

        return EvaluationItem(
            evaluator=self.name,
            code=code,
            severity=actual_severity,
            title=title,
            message=message,
            evidence=evidence or [],
        )

    def create_evidence(
        self,
        metric_name: str,
        value: float,
        threshold: Optional[float] = None,
        comparison: Optional[str] = None,
        unit: Optional[str] = None,
        **context_kwargs,
    ) -> Evidence:
        """Helper to create evidence.

        Args:
            metric_name: Name of the metric
            value: Current value
            threshold: Threshold for comparison
            comparison: Comparison operator
            unit: Unit of measurement
            **context_kwargs: Additional context data

        Returns:
            Evidence
        """
        return Evidence(
            metric_name=metric_name,
            value=value,
            threshold=threshold,
            comparison=comparison,
            unit=unit,
            context=context_kwargs,
        )

    def is_enabled(self, config: Optional[EvaluatorConfig] = None) -> bool:
        """Check if this evaluator is enabled.

        Args:
            config: Override configuration

        Returns:
            True if enabled
        """
        cfg = config or self.config
        return cfg.enabled

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"
