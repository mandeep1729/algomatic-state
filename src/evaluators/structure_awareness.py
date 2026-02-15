"""Structure Awareness Evaluator.

Warns when entry price or trade direction conflicts with key price
levels or the higher-timeframe trend.

Checks:
- SA001: Buying into resistance (entry near resistance levels on LONG)
- SA002: Shorting into support (entry near support levels on SHORT)
- SA003: Entry far from VWAP (entry > N ATR from VWAP)
- SA004: Against higher-timeframe trend
"""

import logging
from typing import Optional

from src.trade.intent import TradeIntent, TradeDirection
from src.trade.evaluation import EvaluationItem, Evidence, Severity
from src.evaluators.context import ContextPack
from src.evaluators.base import Evaluator, EvaluatorConfig
from src.evaluators.registry import register_evaluator
from src.evaluators.evidence import compute_distance_to_level, compare_to_atr
from src.evaluators.regime_fit import BULLISH_LABELS, BEARISH_LABELS

logger = logging.getLogger(__name__)

# Default thresholds
DEFAULT_LEVEL_PROXIMITY_PCT = 0.5
DEFAULT_LEVEL_CRITICAL_PCT = 0.3
DEFAULT_VWAP_ATR_MAX = 2.0


@register_evaluator("structure_awareness")
class StructureAwarenessEvaluator(Evaluator):
    """Evaluates trade entry against key price structure.

    Surfaces warnings when a trade entry is too close to
    resistance/support levels, far from VWAP, or against
    the higher-timeframe trend.
    """

    name = "structure_awareness"
    description = "Evaluates entry against key price levels and HTF trend"

    def evaluate(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: Optional[EvaluatorConfig] = None,
    ) -> list[EvaluationItem]:
        cfg = config or self.config
        items: list[EvaluationItem] = []

        logger.debug(
            "StructureAwareness evaluate: symbol=%s, direction=%s, entry=%.2f",
            intent.symbol, intent.direction.value, intent.entry_price,
        )

        # SA001/SA002: Entry near key levels
        level_items = self._check_key_levels(intent, context, cfg)
        items.extend(level_items)

        # SA003: Entry far from VWAP
        item = self._check_vwap_distance(intent, context, cfg)
        if item:
            items.append(item)

        # SA004: Against HTF trend
        item = self._check_htf_trend(intent, context, cfg)
        if item:
            items.append(item)

        logger.debug(
            "StructureAwareness evaluate complete: %d items generated",
            len(items),
        )
        return items

    def _check_key_levels(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: EvaluatorConfig,
    ) -> list[EvaluationItem]:
        """Check SA001 (buying into resistance) and SA002 (shorting into support)."""
        if context.key_levels is None:
            logger.warning("SA001/SA002 skipped: no key_levels available (no daily bars in database)")
            return []

        proximity_pct = config.get_threshold(
            "level_proximity_pct", DEFAULT_LEVEL_PROXIMITY_PCT
        )
        critical_pct = config.get_threshold(
            "level_critical_pct", DEFAULT_LEVEL_CRITICAL_PCT
        )

        kl = context.key_levels
        items: list[EvaluationItem] = []

        if intent.direction == TradeDirection.LONG:
            resistance_levels = {
                "r1": kl.r1,
                "r2": kl.r2,
                "prior_day_high": kl.prior_day_high,
                "rolling_high_20": kl.rolling_high_20,
            }
            for level_name, level_value in resistance_levels.items():
                if level_value is None:
                    continue
                # Only flag if entry is at or above the level (approaching from below)
                # or very close below it
                distance_pct, evidence = compute_distance_to_level(
                    intent.entry_price, level_value
                )
                if distance_pct <= proximity_pct:
                    severity = (
                        Severity.CRITICAL if distance_pct <= critical_pct
                        else Severity.WARNING
                    )
                    items.append(self.create_item(
                        code="SA001",
                        severity=severity,
                        title="Buying Into Resistance",
                        message=(
                            f"Entry at {intent.entry_price:.2f} is within "
                            f"{distance_pct:.2f}% of resistance level "
                            f"{level_name} ({level_value:.2f}). Price may "
                            f"stall or reverse at this level."
                        ),
                        evidence=[evidence],
                        config=config,
                    ))
                    break  # One SA001 per evaluation is enough

        elif intent.direction == TradeDirection.SHORT:
            support_levels = {
                "s1": kl.s1,
                "s2": kl.s2,
                "prior_day_low": kl.prior_day_low,
                "rolling_low_20": kl.rolling_low_20,
            }
            for level_name, level_value in support_levels.items():
                if level_value is None:
                    continue
                distance_pct, evidence = compute_distance_to_level(
                    intent.entry_price, level_value
                )
                if distance_pct <= proximity_pct:
                    severity = (
                        Severity.CRITICAL if distance_pct <= critical_pct
                        else Severity.WARNING
                    )
                    items.append(self.create_item(
                        code="SA002",
                        severity=severity,
                        title="Shorting Into Support",
                        message=(
                            f"Entry at {intent.entry_price:.2f} is within "
                            f"{distance_pct:.2f}% of support level "
                            f"{level_name} ({level_value:.2f}). Price may "
                            f"bounce at this level."
                        ),
                        evidence=[evidence],
                        config=config,
                    ))
                    break  # One SA002 per evaluation is enough

        return items

    def _check_vwap_distance(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        """Check SA003: Entry far from VWAP."""
        vwap = None
        if context.key_levels is not None:
            vwap = context.key_levels.vwap
        if vwap is None:
            logger.debug("SA003 skipped: no VWAP available")
            return None

        atr = context.atr
        if atr is None or atr <= 0:
            logger.debug("SA003 skipped: no ATR available")
            return None

        vwap_atr_max = config.get_threshold("vwap_atr_max", DEFAULT_VWAP_ATR_MAX)

        distance = abs(intent.entry_price - vwap)
        atr_multiple, evidence = compare_to_atr(distance, atr, "vwap_distance_atr")

        if atr_multiple <= vwap_atr_max:
            return None

        return self.create_item(
            code="SA003",
            severity=config.get_severity("SA003", Severity.WARNING),
            title="Entry Far From VWAP",
            message=(
                f"Entry at {intent.entry_price:.2f} is {atr_multiple:.1f} ATR "
                f"from VWAP ({vwap:.2f}). Extended entries away from VWAP "
                f"carry higher mean-reversion risk."
            ),
            evidence=[evidence],
            config=config,
        )

    def _check_htf_trend(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        """Check SA004: Trade direction against higher-timeframe trend."""
        if context.mtfa is None or context.mtfa.htf_trend is None:
            logger.warning("SA004 skipped: no HTF trend data (no HMM regime states for higher timeframes)")
            return None

        htf_trend = context.mtfa.htf_trend.lower()
        direction = intent.direction

        conflict = False
        if direction == TradeDirection.LONG and htf_trend in BEARISH_LABELS:
            conflict = True
        elif direction == TradeDirection.SHORT and htf_trend in BULLISH_LABELS:
            conflict = True

        if not conflict:
            return None

        return self.create_item(
            code="SA004",
            severity=config.get_severity("SA004", Severity.WARNING),
            title="Against Higher-Timeframe Trend",
            message=(
                f"Your {direction.value} trade opposes the higher-timeframe "
                f"trend ({context.mtfa.htf_trend}). Counter-trend trades "
                f"require stronger setups and tighter risk management."
            ),
            evidence=[
                Evidence(
                    metric_name="htf_trend",
                    value=0.0,
                    context={
                        "htf_trend": context.mtfa.htf_trend,
                        "trade_direction": direction.value,
                    },
                ),
            ],
            config=config,
        )
