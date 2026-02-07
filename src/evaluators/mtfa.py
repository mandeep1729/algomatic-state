"""Multi-Timeframe Alignment Evaluator.

Evaluates whether multiple timeframes agree on market direction
and flags higher-timeframe instability.

Checks:
- MTFA001: Low alignment score (timeframes disagree)
- MTFA002: High alignment score (positive confirmation)
- MTFA003: HTF regime has high transition risk
"""

import logging
from typing import Optional

from src.trade.intent import TradeIntent
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
DEFAULT_LOW_ALIGNMENT_THRESHOLD = 0.6
DEFAULT_HIGH_ALIGNMENT_THRESHOLD = 0.8
DEFAULT_HTF_TRANSITION_RISK_THRESHOLD = 0.3

# Higher timeframes to check for transition risk
HTF_TIMEFRAMES = frozenset({"1Hour", "1Day"})


@register_evaluator("mtfa")
class MTFAEvaluator(Evaluator):
    """Evaluates multi-timeframe alignment for trade context.

    Surfaces concerns when timeframes disagree, and provides
    positive confirmation when they align.
    """

    name = "mtfa"
    description = "Evaluates multi-timeframe alignment"

    def evaluate(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: Optional[EvaluatorConfig] = None,
    ) -> list[EvaluationItem]:
        cfg = config or self.config
        items: list[EvaluationItem] = []

        mtfa = context.mtfa
        if mtfa is None or mtfa.alignment_score is None:
            logger.debug("MTFA evaluate: no mtfa data available")
            return items

        logger.debug(
            "MTFA evaluate: symbol=%s, alignment_score=%.2f, conflicts=%d",
            intent.symbol, mtfa.alignment_score, len(mtfa.conflicts) if mtfa.conflicts else 0,
        )

        low_threshold = cfg.get_threshold(
            "low_alignment_threshold", DEFAULT_LOW_ALIGNMENT_THRESHOLD
        )
        high_threshold = cfg.get_threshold(
            "high_alignment_threshold", DEFAULT_HIGH_ALIGNMENT_THRESHOLD
        )
        htf_transition_threshold = cfg.get_threshold(
            "htf_transition_risk_threshold", DEFAULT_HTF_TRANSITION_RISK_THRESHOLD
        )

        # MTFA001: Low alignment — timeframes disagree
        item = self._check_low_alignment(mtfa.alignment_score, mtfa.conflicts, low_threshold, cfg)
        if item:
            items.append(item)

        # MTFA002: High alignment — positive confirmation
        item = self._check_high_alignment(mtfa.alignment_score, high_threshold, cfg)
        if item:
            items.append(item)

        # MTFA003: HTF has high transition risk
        htf_items = self._check_htf_transition_risk(context, htf_transition_threshold, cfg)
        items.extend(htf_items)

        logger.debug("MTFA evaluate complete: %d items generated", len(items))
        return items

    def _check_low_alignment(
        self,
        alignment_score: float,
        conflicts: list[str],
        threshold: float,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        if alignment_score >= threshold:
            return None

        conflict_detail = ""
        if conflicts:
            conflict_detail = " Conflicts: " + "; ".join(conflicts) + "."

        return self.create_item(
            code="MTFA001",
            severity=config.get_severity("MTFA001", Severity.WARNING),
            title="Timeframe Misalignment",
            message=(
                f"Multi-timeframe alignment is {alignment_score:.0%} "
                f"(threshold: {threshold:.0%}). The timeframes you're "
                f"monitoring are giving mixed signals.{conflict_detail} "
                f"Consider waiting for clearer alignment or reducing "
                f"position size to account for the uncertainty."
            ),
            evidence=[
                Evidence(
                    metric_name="mtfa_alignment_score",
                    value=alignment_score,
                    threshold=threshold,
                    comparison=">=",
                    context={"conflicts": conflicts},
                ),
            ],
            config=config,
        )

    def _check_high_alignment(
        self,
        alignment_score: float,
        threshold: float,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        if alignment_score < threshold:
            return None

        return self.create_item(
            code="MTFA002",
            severity=config.get_severity("MTFA002", Severity.INFO),
            title="Timeframes Aligned",
            message=(
                f"Multi-timeframe alignment is {alignment_score:.0%}. "
                f"The timeframes are showing consistent signals, which "
                f"supports the trade thesis from a multi-timeframe perspective."
            ),
            evidence=[
                Evidence(
                    metric_name="mtfa_alignment_score",
                    value=alignment_score,
                    threshold=threshold,
                    comparison=">=",
                ),
            ],
            config=config,
        )

    def _check_htf_transition_risk(
        self,
        context: ContextPack,
        threshold: float,
        config: EvaluatorConfig,
    ) -> list[EvaluationItem]:
        items = []

        for tf in HTF_TIMEFRAMES:
            regime = context.regimes.get(tf)
            if regime is None or regime.transition_risk is None:
                continue

            if regime.transition_risk > threshold:
                items.append(self.create_item(
                    code="MTFA003",
                    severity=config.get_severity("MTFA003", Severity.WARNING),
                    title=f"HTF Regime Unstable ({tf})",
                    message=(
                        f"The {tf} regime has a {regime.transition_risk:.0%} "
                        f"probability of transitioning (threshold: {threshold:.0%}). "
                        f"Even if the lower timeframe looks clear, instability at "
                        f"the higher timeframe can invalidate shorter-term setups. "
                        f"Consider waiting for the higher timeframe to stabilize."
                    ),
                    evidence=[
                        Evidence(
                            metric_name="htf_transition_risk",
                            value=regime.transition_risk,
                            threshold=threshold,
                            comparison="<=",
                            context={"timeframe": tf},
                        ),
                    ],
                    config=config,
                ))

        return items
