"""Stop Placement Quality Evaluator.

Detects common stop-loss placement mistakes that increase
the risk of being stopped out prematurely.

Checks:
- SP001: Stop at obvious liquidity/sweep level
- SP002: Stop too tight for recent range
- SP003: Stop at last candle extremum
"""

import logging
from typing import Optional

from src.trade.intent import TradeIntent, TradeDirection
from src.trade.evaluation import EvaluationItem, Evidence, Severity
from src.evaluators.context import ContextPack
from src.evaluators.base import Evaluator, EvaluatorConfig
from src.evaluators.registry import register_evaluator
from src.evaluators.evidence import compute_distance_to_level, compare_to_atr

logger = logging.getLogger(__name__)

# Default thresholds
DEFAULT_STOP_LEVEL_PROXIMITY_PCT = 0.3
DEFAULT_MIN_STOP_RANGE_MULTIPLE = 0.5
DEFAULT_LAST_CANDLE_PROXIMITY_PCT = 0.2


@register_evaluator("stop_placement")
class StopPlacementEvaluator(Evaluator):
    """Evaluates the quality of stop-loss placement.

    Surfaces warnings when the stop loss sits at obvious
    liquidity levels, is too tight for recent volatility,
    or mirrors the last candle's extremum exactly.
    """

    name = "stop_placement"
    description = "Detects poor stop-loss placement patterns"

    def evaluate(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: Optional[EvaluatorConfig] = None,
    ) -> list[EvaluationItem]:
        cfg = config or self.config
        items: list[EvaluationItem] = []

        logger.debug(
            "StopPlacement evaluate: symbol=%s, direction=%s, stop=%.2f",
            intent.symbol, intent.direction.value, intent.stop_loss,
        )

        # SP001: Stop at obvious liquidity level
        item = self._check_liquidity_level(intent, context, cfg)
        if item:
            items.append(item)

        # SP002: Stop too tight for recent range
        item = self._check_stop_range(intent, context, cfg)
        if item:
            items.append(item)

        # SP003: Stop at last candle extremum
        item = self._check_last_candle(intent, context, cfg)
        if item:
            items.append(item)

        logger.debug(
            "StopPlacement evaluate complete: %d items generated",
            len(items),
        )
        return items

    def _check_liquidity_level(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        """Check SP001: Stop at obvious liquidity/sweep level."""
        if context.key_levels is None:
            logger.debug("SP001 skipped: no key_levels")
            return None

        proximity_pct = config.get_threshold(
            "stop_level_proximity_pct", DEFAULT_STOP_LEVEL_PROXIMITY_PCT
        )

        kl = context.key_levels

        # For longs, stops below entry — check proximity to support levels
        # that act as liquidity magnets
        if intent.direction == TradeDirection.LONG:
            sweep_levels = {
                "prior_day_low": kl.prior_day_low,
                "rolling_low_20": kl.rolling_low_20,
            }
        else:
            sweep_levels = {
                "prior_day_high": kl.prior_day_high,
                "rolling_high_20": kl.rolling_high_20,
            }

        for level_name, level_value in sweep_levels.items():
            if level_value is None:
                continue
            distance_pct, evidence = compute_distance_to_level(
                intent.stop_loss, level_value
            )
            if distance_pct <= proximity_pct:
                return self.create_item(
                    code="SP001",
                    severity=config.get_severity("SP001", Severity.WARNING),
                    title="Stop at Obvious Liquidity Level",
                    message=(
                        f"Stop at {intent.stop_loss:.2f} is within "
                        f"{distance_pct:.2f}% of {level_name} "
                        f"({level_value:.2f}). Stops clustered at obvious "
                        f"levels are frequently swept before price reverses."
                    ),
                    evidence=[evidence],
                    config=config,
                )

        return None

    def _check_stop_range(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        """Check SP002: Stop too tight for recent range."""
        atr = context.atr
        if atr is None or atr <= 0:
            logger.debug("SP002 skipped: no ATR available")
            return None

        min_multiple = config.get_threshold(
            "min_stop_range_multiple", DEFAULT_MIN_STOP_RANGE_MULTIPLE
        )

        stop_distance = abs(intent.entry_price - intent.stop_loss)
        atr_multiple, evidence = compare_to_atr(
            stop_distance, atr, "stop_range_atr_multiple"
        )

        if atr_multiple >= min_multiple:
            return None

        return self.create_item(
            code="SP002",
            severity=config.get_severity("SP002", Severity.WARNING),
            title="Stop Too Tight for Recent Range",
            message=(
                f"Stop distance ({stop_distance:.2f}) is only "
                f"{atr_multiple:.2f}x the recent average range "
                f"(ATR: {atr:.2f}). A stop tighter than "
                f"{min_multiple:.1f}x ATR is easily hit by normal "
                f"price fluctuations."
            ),
            evidence=[evidence],
            config=config,
        )

    def _check_last_candle(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        """Check SP003: Stop at last candle extremum."""
        bars = context.primary_bars
        if bars is None or bars.empty:
            logger.debug("SP003 skipped: no primary bars")
            return None

        proximity_pct = config.get_threshold(
            "last_candle_proximity_pct", DEFAULT_LAST_CANDLE_PROXIMITY_PCT
        )

        last_bar = bars.iloc[-1]

        if intent.direction == TradeDirection.LONG:
            extremum = float(last_bar["low"])
            extremum_name = "last bar low"
        else:
            extremum = float(last_bar["high"])
            extremum_name = "last bar high"

        distance_pct, evidence = compute_distance_to_level(
            intent.stop_loss, extremum
        )

        if distance_pct > proximity_pct:
            return None

        return self.create_item(
            code="SP003",
            severity=config.get_severity("SP003", Severity.INFO),
            title="Stop at Last Candle Extremum",
            message=(
                f"Stop at {intent.stop_loss:.2f} is within "
                f"{distance_pct:.2f}% of the {extremum_name} "
                f"({extremum:.2f}). Many traders place stops at the "
                f"same obvious level, making it a target for stop runs."
            ),
            evidence=[evidence],
            config=config,
        )
