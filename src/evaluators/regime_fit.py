"""Regime Fit Evaluator.

Evaluates whether the proposed trade direction aligns with the
current market regime and flags regime instability signals.

Checks:
- REG001: Trade direction conflicts with regime label
- REG002: High transition risk (regime may be shifting)
- REG003: High entropy (uncertain regime)
- REG004: OOD detected (market outside model training range)
"""

import logging
from typing import Optional

from src.trade.intent import TradeIntent, TradeDirection
from src.trade.evaluation import (
    EvaluationItem,
    Evidence,
    Severity,
)
from src.evaluators.context import ContextPack
from src.evaluators.base import Evaluator, EvaluatorConfig
from src.evaluators.registry import register_evaluator

logger = logging.getLogger(__name__)

# Default thresholds
DEFAULT_TRANSITION_RISK_THRESHOLD = 0.3
DEFAULT_ENTROPY_THRESHOLD = 1.5

# Directional label sets for regime conflict detection
BULLISH_LABELS = frozenset({
    "up_trending", "bullish", "trending_up", "bull", "uptrend",
    "strong_up", "momentum_up",
})
BEARISH_LABELS = frozenset({
    "down_trending", "bearish", "trending_down", "bear", "downtrend",
    "strong_down", "momentum_down",
})


def _is_generic_label(label: Optional[str]) -> bool:
    """Check if a state label is generic (state_N pattern)."""
    if label is None:
        return True
    return label.startswith("state_")


@register_evaluator("regime_fit")
class RegimeFitEvaluator(Evaluator):
    """Evaluates trade fit against the current market regime.

    Surfaces concerns when a trade direction conflicts with the
    detected regime, or when regime data signals instability.
    """

    name = "regime_fit"
    description = "Evaluates trade alignment with market regime"

    def evaluate(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: Optional[EvaluatorConfig] = None,
    ) -> list[EvaluationItem]:
        cfg = config or self.config
        items: list[EvaluationItem] = []

        regime = context.primary_regime
        if regime is None:
            logger.debug("RegimeFit evaluate: no regime data available")
            return items

        logger.debug(
            "RegimeFit evaluate: symbol=%s, direction=%s, regime=%s, transition_risk=%s",
            intent.symbol, intent.direction.value,
            regime.state_label, regime.transition_risk,
        )

        transition_threshold = cfg.get_threshold(
            "transition_risk_threshold", DEFAULT_TRANSITION_RISK_THRESHOLD
        )
        entropy_threshold = cfg.get_threshold(
            "entropy_threshold", DEFAULT_ENTROPY_THRESHOLD
        )

        # REG001: Direction conflicts with regime label
        item = self._check_direction_conflict(intent, regime.state_label, cfg)
        if item:
            items.append(item)

        # REG002: High transition risk
        item = self._check_transition_risk(regime.transition_risk, transition_threshold, cfg)
        if item:
            items.append(item)

        # REG003: High entropy
        item = self._check_entropy(regime.entropy, entropy_threshold, cfg)
        if item:
            items.append(item)

        # REG004: OOD detected
        item = self._check_ood(regime.is_ood, cfg)
        if item:
            items.append(item)

        logger.debug("RegimeFit evaluate complete: %d items generated", len(items))
        return items

    def _check_direction_conflict(
        self,
        intent: TradeIntent,
        state_label: Optional[str],
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        if _is_generic_label(state_label):
            return None

        label_lower = state_label.lower()
        direction = intent.direction

        conflict = False
        if direction == TradeDirection.LONG and label_lower in BEARISH_LABELS:
            conflict = True
        elif direction == TradeDirection.SHORT and label_lower in BULLISH_LABELS:
            conflict = True

        if not conflict:
            return None

        return self.create_item(
            code="REG001",
            severity=config.get_severity("REG001", Severity.WARNING),
            title="Trade Direction Conflicts with Regime",
            message=(
                f"Your {direction.value} trade may conflict with the current "
                f"regime ({state_label}). The market regime suggests a different "
                f"directional bias. Consider whether your setup has a specific "
                f"edge that overrides the broader regime context."
            ),
            evidence=[
                Evidence(
                    metric_name="regime_label",
                    value=0.0,
                    context={
                        "state_label": state_label,
                        "trade_direction": direction.value,
                    },
                ),
            ],
            config=config,
        )

    def _check_transition_risk(
        self,
        transition_risk: Optional[float],
        threshold: float,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        if transition_risk is None:
            return None

        if transition_risk <= threshold:
            return None

        return self.create_item(
            code="REG002",
            severity=config.get_severity("REG002", Severity.WARNING),
            title="Elevated Regime Transition Risk",
            message=(
                f"The current regime has a {transition_risk:.0%} probability of "
                f"transitioning to a different state (threshold: {threshold:.0%}). "
                f"This suggests the market may be shifting. Consider tighter risk "
                f"management or waiting for the regime to stabilize."
            ),
            evidence=[
                Evidence(
                    metric_name="transition_risk",
                    value=transition_risk,
                    threshold=threshold,
                    comparison="<=",
                ),
            ],
            config=config,
        )

    def _check_entropy(
        self,
        entropy: Optional[float],
        threshold: float,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        if entropy is None:
            return None

        if entropy <= threshold:
            return None

        return self.create_item(
            code="REG003",
            severity=config.get_severity("REG003", Severity.INFO),
            title="Uncertain Regime Classification",
            message=(
                f"Regime entropy is {entropy:.2f} (threshold: {threshold:.2f}), "
                f"indicating the model is less certain about the current market "
                f"state. In ambiguous regimes, consider reducing position size "
                f"or requiring additional confirmation before entering."
            ),
            evidence=[
                Evidence(
                    metric_name="regime_entropy",
                    value=entropy,
                    threshold=threshold,
                    comparison="<=",
                    unit="nats",
                ),
            ],
            config=config,
        )

    def _check_ood(
        self,
        is_ood: bool,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        if not is_ood:
            return None

        return self.create_item(
            code="REG004",
            severity=config.get_severity("REG004", Severity.WARNING),
            title="Out-of-Distribution Market Behavior",
            message=(
                "The current market observation falls outside the model's "
                "training distribution. This means the regime classification "
                "may be unreliable. Exercise extra caution and rely more on "
                "your own analysis and risk management rules."
            ),
            evidence=[
                Evidence(
                    metric_name="is_ood",
                    value=1.0,
                    context={"description": "Market behavior outside model training range"},
                ),
            ],
            config=config,
        )
