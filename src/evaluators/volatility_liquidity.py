"""Volatility & Liquidity Evaluator.

Flags conditions where low volume or extreme candle range
make trade entries riskier.

Checks:
- VL001: Low relative volume (relvol below threshold)
- VL002: Extended candle entry (bar range z-score above threshold)
"""

import logging
from typing import Optional

from src.trade.intent import TradeIntent
from src.trade.evaluation import EvaluationItem, Evidence, Severity
from src.evaluators.context import ContextPack
from src.evaluators.base import Evaluator, EvaluatorConfig
from src.evaluators.registry import register_evaluator

logger = logging.getLogger(__name__)

# Default thresholds
DEFAULT_MIN_RELATIVE_VOLUME = 0.5
DEFAULT_EXTENDED_CANDLE_ZSCORE = 2.0
DEFAULT_EXTENDED_CANDLE_CRITICAL_ZSCORE = 3.0


@register_evaluator("volatility_liquidity")
class VolatilityLiquidityEvaluator(Evaluator):
    """Evaluates volume and volatility conditions around entry.

    Surfaces warnings when the market is thinly traded or when
    the current bar shows extreme range expansion.
    """

    name = "volatility_liquidity"
    description = "Flags low volume and extended candle conditions"

    def evaluate(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: Optional[EvaluatorConfig] = None,
    ) -> list[EvaluationItem]:
        cfg = config or self.config
        items: list[EvaluationItem] = []

        logger.debug(
            "VolatilityLiquidity evaluate: symbol=%s",
            intent.symbol,
        )

        # VL001: Low relative volume
        item = self._check_relative_volume(intent, context, cfg)
        if item:
            items.append(item)

        # VL002: Extended candle
        item = self._check_extended_candle(intent, context, cfg)
        if item:
            items.append(item)

        logger.debug(
            "VolatilityLiquidity evaluate complete: %d items generated",
            len(items),
        )
        return items

    def _check_relative_volume(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        """Check VL001: Low relative volume."""
        relvol = context.get_feature("relvol_60")
        if relvol is None:
            logger.debug("VL001 skipped: relvol_60 feature not available")
            return None

        min_relvol = config.get_threshold(
            "min_relative_volume", DEFAULT_MIN_RELATIVE_VOLUME
        )

        if relvol >= min_relvol:
            return None

        return self.create_item(
            code="VL001",
            severity=config.get_severity("VL001", Severity.WARNING),
            title="Low Relative Volume",
            message=(
                f"Relative volume is {relvol:.2f}x the 60-bar average "
                f"(threshold: {min_relvol:.2f}x). Low volume can lead to "
                f"wider spreads, poor fills, and unreliable price action."
            ),
            evidence=[
                Evidence(
                    metric_name="relative_volume",
                    value=relvol,
                    threshold=min_relvol,
                    comparison=">=",
                    unit="x",
                ),
            ],
            config=config,
        )

    def _check_extended_candle(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        """Check VL002: Extended candle (high range z-score)."""
        range_z = context.get_feature("range_z_60")
        if range_z is None:
            logger.warning("VL002 skipped: range_z_60 feature not available (feature not computed/stored)")
            return None

        zscore_threshold = config.get_threshold(
            "extended_candle_zscore", DEFAULT_EXTENDED_CANDLE_ZSCORE
        )
        critical_zscore = config.get_threshold(
            "extended_candle_critical_zscore", DEFAULT_EXTENDED_CANDLE_CRITICAL_ZSCORE
        )

        if range_z <= zscore_threshold:
            return None

        severity = (
            Severity.CRITICAL if range_z > critical_zscore
            else Severity.WARNING
        )

        return self.create_item(
            code="VL002",
            severity=severity,
            title="Extended Candle Entry",
            message=(
                f"Current bar range z-score is {range_z:.1f} "
                f"(threshold: {zscore_threshold:.1f}). Entering after an "
                f"extended candle increases the risk of mean reversion "
                f"and poor entry timing."
            ),
            evidence=[
                Evidence(
                    metric_name="range_zscore",
                    value=range_z,
                    threshold=zscore_threshold,
                    comparison="<=",
                    unit="z",
                ),
            ],
            config=config,
        )
