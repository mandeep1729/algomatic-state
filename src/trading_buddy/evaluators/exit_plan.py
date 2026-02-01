"""Exit Plan Evaluator.

Evaluates the exit plan of a trade intent:
- Verifies stop loss and profit target are defined
- Checks logical coherence of exit levels
- Validates exit placement relative to key levels

This evaluator helps traders ensure they have a complete
exit plan before entering a trade.
"""

import logging
from typing import Optional

from src.trading_buddy.domain import (
    TradeIntent,
    TradeDirection,
    EvaluationItem,
    Evidence,
    Severity,
)
from src.trading_buddy.context import ContextPack
from src.trading_buddy.evaluators.base import Evaluator, EvaluatorConfig
from src.trading_buddy.evaluators.registry import register_evaluator
from src.trading_buddy.evaluators.evidence import format_currency, format_percentage

logger = logging.getLogger(__name__)


# Thresholds for proximity warnings
DEFAULT_LEVEL_PROXIMITY_PCT = 0.5  # Warn if exit within 0.5% of key level


@register_evaluator("exit_plan")
class ExitPlanEvaluator(Evaluator):
    """Evaluates the exit plan of a trade intent.

    Checks:
    - EP001: Missing stop loss
    - EP002: Missing profit target
    - EP003: Stop loss on wrong side of entry (incoherent)
    - EP004: Profit target on wrong side of entry (incoherent)
    - EP005: Stop loss near key support/resistance
    - EP006: Target near key resistance/support

    This evaluator ensures traders have thought through their
    exit plan before entering, without predicting outcomes.
    """

    name = "exit_plan"
    description = "Validates exit plan completeness and coherence"

    def evaluate(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: Optional[EvaluatorConfig] = None,
    ) -> list[EvaluationItem]:
        """Evaluate exit plan completeness and coherence.

        Args:
            intent: Trade intent to evaluate
            context: Market context with key levels
            config: Optional configuration overrides

        Returns:
            List of evaluation findings
        """
        cfg = config or self.config
        items: list[EvaluationItem] = []

        # EP001/EP002: Check for missing exits
        # Note: TradeIntent requires these, but check for zero/None edge cases
        missing_items = self._check_missing_exits(intent, cfg)
        items.extend(missing_items)

        # EP003/EP004: Check coherence
        # Note: TradeIntent validates this in __post_init__, but we can
        # provide additional guidance if values are very close
        coherence_items = self._check_exit_coherence(intent, cfg)
        items.extend(coherence_items)

        # EP005/EP006: Check proximity to key levels
        if context.key_levels:
            level_items = self._check_key_level_proximity(intent, context, cfg)
            items.extend(level_items)

        # Add informational item about exit plan if everything is good
        if not items:
            items.append(self.create_item(
                code="EP000",
                severity=Severity.INFO,
                title="Exit Plan Complete",
                message=(
                    f"Stop loss at {format_currency(intent.stop_loss)} and "
                    f"target at {format_currency(intent.profit_target)} are properly defined."
                ),
                evidence=[
                    Evidence(
                        metric_name="stop_loss",
                        value=intent.stop_loss,
                    ),
                    Evidence(
                        metric_name="profit_target",
                        value=intent.profit_target,
                    ),
                ],
                config=cfg,
            ))

        return items

    def _check_missing_exits(
        self,
        intent: TradeIntent,
        config: EvaluatorConfig,
    ) -> list[EvaluationItem]:
        """Check for missing or zero exit levels.

        Args:
            intent: Trade intent
            config: Evaluator config

        Returns:
            List of items for missing exits
        """
        items = []

        # TradeIntent requires these, but check for edge cases
        if intent.stop_loss <= 0:
            items.append(self.create_item(
                code="EP001",
                severity=config.get_severity("EP001", Severity.BLOCKER),
                title="Missing Stop Loss",
                message=(
                    "No stop loss defined. Every trade should have a predetermined "
                    "exit point to limit losses. Define where you'll exit if the "
                    "trade moves against you."
                ),
                evidence=[],
                config=config,
            ))

        if intent.profit_target <= 0:
            items.append(self.create_item(
                code="EP002",
                severity=config.get_severity("EP002", Severity.WARNING),
                title="Missing Profit Target",
                message=(
                    "No profit target defined. While not always required, having "
                    "a target helps with trade management and ensures you have "
                    "a plan for taking profits."
                ),
                evidence=[],
                config=config,
            ))

        return items

    def _check_exit_coherence(
        self,
        intent: TradeIntent,
        config: EvaluatorConfig,
    ) -> list[EvaluationItem]:
        """Check logical coherence of exit levels.

        Args:
            intent: Trade intent
            config: Evaluator config

        Returns:
            List of items for coherence issues
        """
        items = []

        # Check stop vs entry gap (warn if very tight)
        stop_gap_pct = abs(intent.entry_price - intent.stop_loss) / intent.entry_price * 100
        target_gap_pct = abs(intent.profit_target - intent.entry_price) / intent.entry_price * 100

        # Very tight stop (less than 0.1%)
        if stop_gap_pct < 0.1:
            items.append(self.create_item(
                code="EP003",
                severity=config.get_severity("EP003", Severity.CRITICAL),
                title="Stop Loss Extremely Close to Entry",
                message=(
                    f"Stop is only {format_percentage(stop_gap_pct)} from entry. "
                    f"This may result in immediate stop-out from normal market noise. "
                    f"Verify this is intentional."
                ),
                evidence=[
                    Evidence(
                        metric_name="stop_gap_percentage",
                        value=stop_gap_pct,
                        threshold=0.1,
                        comparison=">=",
                        unit="%",
                    ),
                ],
                config=config,
            ))

        # Very tight target (less than 0.1%)
        if target_gap_pct < 0.1:
            items.append(self.create_item(
                code="EP004",
                severity=config.get_severity("EP004", Severity.WARNING),
                title="Profit Target Extremely Close to Entry",
                message=(
                    f"Target is only {format_percentage(target_gap_pct)} from entry. "
                    f"After spreads and commissions, the net profit may be minimal. "
                    f"Verify this scalp-style trade is appropriate."
                ),
                evidence=[
                    Evidence(
                        metric_name="target_gap_percentage",
                        value=target_gap_pct,
                        threshold=0.1,
                        comparison=">=",
                        unit="%",
                    ),
                ],
                config=config,
            ))

        return items

    def _check_key_level_proximity(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: EvaluatorConfig,
    ) -> list[EvaluationItem]:
        """Check if exits are near key levels.

        Args:
            intent: Trade intent
            context: Market context with key levels
            config: Evaluator config

        Returns:
            List of items for level proximity issues
        """
        items = []
        levels = context.key_levels

        if not levels:
            return items

        proximity_threshold = config.get_threshold(
            "level_proximity_pct", DEFAULT_LEVEL_PROXIMITY_PCT
        )

        # Check stop loss proximity to levels
        stop_level, stop_distance = levels.distance_to_nearest_level(intent.stop_loss)
        if stop_distance < proximity_threshold and stop_level != "none":
            # For longs, stop near support is good; stop near resistance is concerning
            # For shorts, stop near resistance is good; stop near support is concerning
            is_concerning = self._is_stop_level_concerning(
                intent.direction, stop_level
            )

            if is_concerning:
                items.append(self.create_item(
                    code="EP005",
                    severity=config.get_severity("EP005", Severity.INFO),
                    title="Stop Near Key Level",
                    message=(
                        f"Stop loss is {format_percentage(stop_distance)} from {stop_level}. "
                        f"Key levels often act as magnets for price. Consider whether "
                        f"placing stop slightly beyond this level would be more appropriate."
                    ),
                    evidence=[
                        Evidence(
                            metric_name="stop_to_level_distance",
                            value=stop_distance,
                            threshold=proximity_threshold,
                            comparison=">=",
                            unit="%",
                            context={"level_name": stop_level},
                        ),
                    ],
                    config=config,
                ))

        # Check profit target proximity to levels
        target_level, target_distance = levels.distance_to_nearest_level(intent.profit_target)
        if target_distance < proximity_threshold and target_level != "none":
            # For longs, target at/near resistance is good
            # For shorts, target at/near support is good
            is_good_placement = self._is_target_level_good(
                intent.direction, target_level
            )

            if is_good_placement:
                items.append(self.create_item(
                    code="EP006",
                    severity=config.get_severity("EP006", Severity.INFO),
                    title="Target at Key Level",
                    message=(
                        f"Profit target is near {target_level}. "
                        f"This is often a logical place to take profits as price "
                        f"may find resistance/support at this level."
                    ),
                    evidence=[
                        Evidence(
                            metric_name="target_to_level_distance",
                            value=target_distance,
                            unit="%",
                            context={"level_name": target_level},
                        ),
                    ],
                    config=config,
                ))

        return items

    def _is_stop_level_concerning(
        self,
        direction: TradeDirection,
        level_name: str,
    ) -> bool:
        """Check if stop placement relative to level is concerning.

        Args:
            direction: Trade direction
            level_name: Name of nearby level

        Returns:
            True if placement might be problematic
        """
        resistance_levels = {"r1", "r2", "prior_day_high", "rolling_high_20"}
        support_levels = {"s1", "s2", "prior_day_low", "rolling_low_20"}

        if direction == TradeDirection.LONG:
            # For longs, stop near resistance (above entry) would be wrong
            # Stop near support is expected
            return level_name in resistance_levels
        else:
            # For shorts, stop near support (below entry) would be wrong
            # Stop near resistance is expected
            return level_name in support_levels

    def _is_target_level_good(
        self,
        direction: TradeDirection,
        level_name: str,
    ) -> bool:
        """Check if target placement relative to level is good.

        Args:
            direction: Trade direction
            level_name: Name of nearby level

        Returns:
            True if placement is logically sound
        """
        resistance_levels = {"r1", "r2", "prior_day_high", "rolling_high_20"}
        support_levels = {"s1", "s2", "prior_day_low", "rolling_low_20"}

        if direction == TradeDirection.LONG:
            # For longs, target at resistance is logical
            return level_name in resistance_levels
        else:
            # For shorts, target at support is logical
            return level_name in support_levels
