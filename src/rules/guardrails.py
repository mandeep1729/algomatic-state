"""Guardrails for Trading Buddy output.

Ensures all output adheres to the non-predictive philosophy:
- No price predictions
- No probability claims
- No buy/sell signals
- Focus on risk and process, not outcomes

Also provides reusable warning templates for common risk scenarios.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from src.trade.evaluation import (
    EvaluationResult,
    EvaluationItem,
    Severity,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Prohibited Patterns
# =============================================================================

# Patterns that suggest price prediction
PREDICTION_PATTERNS = [
    r"\bwill\s+(go|move|rise|fall|drop|increase|decrease)\b",
    r"\bprice\s+will\b",
    r"\bexpect(ed|ing)?\s+to\s+(reach|hit|break)\b",
    r"\bshould\s+(reach|hit|go)\b",
    r"\blikely\s+to\s+(rise|fall|break|reach)\b",
    r"\bhigh\s+probability\b",
    r"\b(guaranteed|certain|definite)\b",
    r"\bbuy\s+signal\b",
    r"\bsell\s+signal\b",
    r"\bstrong\s+buy\b",
    r"\bstrong\s+sell\b",
]

# Compiled patterns for efficiency
_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in PREDICTION_PATTERNS]


def contains_prediction(text: str) -> bool:
    """Check if text contains predictive language.

    Args:
        text: Text to check

    Returns:
        True if predictive language detected
    """
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            return True
    return False


def sanitize_message(text: str) -> str:
    """Remove or rephrase predictive language in a message.

    This is a safety net - evaluators should not produce
    predictive language in the first place.

    Args:
        text: Original message text

    Returns:
        Sanitized message
    """
    # Replace common predictive phrases with risk-focused alternatives
    replacements = [
        (r"\bwill go up\b", "may face upward pressure"),
        (r"\bwill go down\b", "may face downward pressure"),
        (r"\bwill rise\b", "could move higher"),
        (r"\bwill fall\b", "could move lower"),
        (r"\bprice will\b", "price may"),
        (r"\bexpect(ed)? to reach\b", "has potential to reach"),
        (r"\bshould reach\b", "may approach"),
        (r"\bhigh probability\b", "increased likelihood based on historical patterns"),
        (r"\bguaranteed\b", "possible"),
        (r"\bcertain\b", "potential"),
    ]

    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    return result


def validate_evaluation_result(result: EvaluationResult) -> list[str]:
    """Validate an evaluation result for prohibited content.

    Args:
        result: Evaluation result to validate

    Returns:
        List of validation warnings (empty if clean)
    """
    warnings = []

    # Check summary
    if contains_prediction(result.summary):
        warnings.append(f"Summary contains predictive language: '{result.summary[:50]}...'")

    # Check each item
    for item in result.items:
        if contains_prediction(item.message):
            warnings.append(
                f"Item {item.code} message contains predictive language: "
                f"'{item.message[:50]}...'"
            )
        if contains_prediction(item.title):
            warnings.append(
                f"Item {item.code} title contains predictive language: '{item.title}'"
            )

    return warnings


def sanitize_evaluation_result(result: EvaluationResult) -> EvaluationResult:
    """Sanitize an evaluation result to remove predictive language.

    Args:
        result: Original evaluation result

    Returns:
        Sanitized evaluation result
    """
    # Sanitize summary
    sanitized_summary = sanitize_message(result.summary)

    # Sanitize items
    sanitized_items = []
    for item in result.items:
        sanitized_item = EvaluationItem(
            evaluator=item.evaluator,
            code=item.code,
            severity=item.severity,
            title=sanitize_message(item.title),
            message=sanitize_message(item.message),
            evidence=item.evidence,
        )
        sanitized_items.append(sanitized_item)

    return EvaluationResult(
        intent=result.intent,
        score=result.score,
        items=sanitized_items,
        summary=sanitized_summary,
        evaluated_at=result.evaluated_at,
        evaluators_run=result.evaluators_run,
        evaluation_id=result.evaluation_id,
    )


# =============================================================================
# Warning Templates
# =============================================================================

@dataclass
class WarningTemplate:
    """Template for common warning messages.

    Provides consistent, non-predictive messaging for
    common risk scenarios.
    """

    code: str
    title: str
    message_template: str
    severity: Severity

    def format(self, **kwargs) -> tuple[str, str]:
        """Format the template with provided values.

        Args:
            **kwargs: Values to substitute in template

        Returns:
            Tuple of (title, formatted_message)
        """
        return self.title, self.message_template.format(**kwargs)


# Pre-defined warning templates for common scenarios
WARNING_TEMPLATES = {
    # Risk/Reward warnings
    "low_rr": WarningTemplate(
        code="RR001",
        title="Low Risk/Reward Ratio",
        message_template=(
            "Risk/reward ratio of {ratio:.2f}:1 is below the {threshold:.1f}:1 minimum. "
            "This trade requires a higher win rate to be profitable over time. "
            "Consider adjusting your entry, stop, or target."
        ),
        severity=Severity.WARNING,
    ),
    "negative_rr": WarningTemplate(
        code="RR001",
        title="Negative Risk/Reward",
        message_template=(
            "Risk ({risk}) exceeds potential reward ({reward}). "
            "You're risking more than you stand to gain. "
            "Review your trade parameters before proceeding."
        ),
        severity=Severity.BLOCKER,
    ),
    "excessive_risk": WarningTemplate(
        code="RR002",
        title="Excessive Position Risk",
        message_template=(
            "This trade risks {risk_pct:.1f}% of your account, exceeding "
            "your {max_pct:.1f}% limit. Consider reducing position size "
            "to {suggested_size:.0f} shares to stay within risk parameters."
        ),
        severity=Severity.CRITICAL,
    ),

    # Stop loss warnings
    "tight_stop": WarningTemplate(
        code="RR003",
        title="Tight Stop Loss",
        message_template=(
            "Stop is {atr_mult:.2f}x ATR from entry (minimum: {min_mult:.1f}x). "
            "Very tight stops may get triggered by normal market fluctuation. "
            "Consider whether this gives the trade enough room to work."
        ),
        severity=Severity.WARNING,
    ),
    "wide_stop": WarningTemplate(
        code="RR004",
        title="Wide Stop Loss",
        message_template=(
            "Stop is {atr_mult:.2f}x ATR from entry (maximum: {max_mult:.1f}x). "
            "Wide stops increase dollar risk per share. Consider refining "
            "entry timing or reducing position size to manage total risk."
        ),
        severity=Severity.WARNING,
    ),

    # Position sizing warnings
    "large_position": WarningTemplate(
        code="RR005",
        title="Large Position Size",
        message_template=(
            "Position represents {position_pct:.1f}% of account (limit: {max_pct:.1f}%). "
            "High concentration increases portfolio volatility. "
            "Ensure this is intentional and aligns with your strategy."
        ),
        severity=Severity.WARNING,
    ),

    # Volatility warnings
    "high_volatility": WarningTemplate(
        code="VOL001",
        title="Elevated Volatility",
        message_template=(
            "Current volatility ({vol_percentile:.0f}th percentile) is elevated. "
            "Consider whether your stop and position size account for "
            "the increased price movement. Wider stops or smaller size may be prudent."
        ),
        severity=Severity.INFO,
    ),
    "low_volatility": WarningTemplate(
        code="VOL002",
        title="Low Volatility Environment",
        message_template=(
            "Volatility is compressed ({vol_percentile:.0f}th percentile). "
            "Low volatility often precedes expansion. Be prepared for "
            "increased movement and potential stop-outs if volatility rises."
        ),
        severity=Severity.INFO,
    ),

    # Regime warnings
    "counter_trend": WarningTemplate(
        code="REG001",
        title="Counter-Trend Trade",
        message_template=(
            "This {direction} trade is against the current {regime} regime. "
            "Counter-trend trades can work but require careful risk management. "
            "Ensure your thesis accounts for the prevailing market condition."
        ),
        severity=Severity.WARNING,
    ),
    "regime_transition": WarningTemplate(
        code="REG002",
        title="Regime Uncertainty",
        message_template=(
            "Regime transition probability is elevated ({transition_prob:.0f}%). "
            "The market may be shifting states. Consider whether this is "
            "the right time to enter, or wait for regime to stabilize."
        ),
        severity=Severity.INFO,
    ),

    # General caution
    "missing_data": WarningTemplate(
        code="DATA001",
        title="Incomplete Market Context",
        message_template=(
            "Unable to load {data_type} for full evaluation. "
            "Some checks were skipped. Results may be incomplete. "
            "Proceed with additional caution."
        ),
        severity=Severity.WARNING,
    ),
}


def get_warning_template(key: str) -> Optional[WarningTemplate]:
    """Get a warning template by key.

    Args:
        key: Template key

    Returns:
        WarningTemplate or None
    """
    return WARNING_TEMPLATES.get(key)


def format_warning(key: str, **kwargs) -> Optional[tuple[str, str, Severity]]:
    """Format a warning template with provided values.

    Args:
        key: Template key
        **kwargs: Values to substitute

    Returns:
        Tuple of (title, message, severity) or None if template not found
    """
    template = get_warning_template(key)
    if template is None:
        return None

    title, message = template.format(**kwargs)
    return title, message, template.severity
