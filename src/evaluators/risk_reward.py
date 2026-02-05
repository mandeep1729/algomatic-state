"""Risk and Reward Evaluator.

Evaluates trade intent risk/reward characteristics:
- Risk:Reward ratio against minimum thresholds
- Position size vs account risk limits
- Stop loss distance relative to ATR/volatility

This is a core safety evaluator that surfaces potential issues
with trade sizing and risk management.
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
from src.evaluators.evidence import (
    check_threshold,
    compare_to_atr,
    format_ratio,
    format_percentage,
    format_currency,
)

logger = logging.getLogger(__name__)


# Default thresholds
DEFAULT_MIN_RR_RATIO = 2.0
DEFAULT_MAX_RISK_PER_TRADE_PCT = 2.0  # 2% of account
DEFAULT_MIN_STOP_ATR_MULTIPLE = 0.5  # Stop should be at least 0.5 ATR
DEFAULT_MAX_STOP_ATR_MULTIPLE = 3.0  # Stop shouldn't be more than 3 ATR
DEFAULT_MAX_POSITION_SIZE_PCT = 10.0  # 10% of account in single position


@register_evaluator("risk_reward")
class RiskRewardEvaluator(Evaluator):
    """Evaluates risk/reward characteristics of a trade intent.

    Checks:
    - RR001: Risk:Reward ratio too low
    - RR002: Position risk exceeds account limits
    - RR003: Stop loss too tight (< min ATR multiple)
    - RR004: Stop loss too wide (> max ATR multiple)
    - RR005: Position size too large (% of account)

    This evaluator surfaces risk concerns without predicting
    trade outcomes - it helps traders see if their risk
    parameters are within their own defined limits.
    """

    name = "risk_reward"
    description = "Evaluates risk/reward ratio and position sizing"

    def evaluate(
        self,
        intent: TradeIntent,
        context: ContextPack,
        config: Optional[EvaluatorConfig] = None,
    ) -> list[EvaluationItem]:
        """Evaluate risk/reward characteristics.

        Args:
            intent: Trade intent to evaluate
            context: Market context with ATR and other data
            config: Optional configuration overrides

        Returns:
            List of evaluation findings
        """
        logger.debug(
            "Evaluating risk/reward for %s: entry=%.2f, stop=%.2f, target=%.2f, R:R=%.2f",
            intent.symbol, intent.entry_price, intent.stop_loss,
            intent.profit_target, intent.risk_reward_ratio
        )
        cfg = config or self.config
        items: list[EvaluationItem] = []

        # Get thresholds from config or defaults
        min_rr = cfg.get_threshold("min_rr_ratio", DEFAULT_MIN_RR_RATIO)
        max_risk_pct = cfg.get_threshold("max_risk_per_trade_pct", DEFAULT_MAX_RISK_PER_TRADE_PCT)
        min_stop_atr = cfg.get_threshold("min_stop_atr_multiple", DEFAULT_MIN_STOP_ATR_MULTIPLE)
        max_stop_atr = cfg.get_threshold("max_stop_atr_multiple", DEFAULT_MAX_STOP_ATR_MULTIPLE)
        max_position_pct = cfg.get_threshold("max_position_size_pct", DEFAULT_MAX_POSITION_SIZE_PCT)

        # Get account balance from config if available
        account_balance = cfg.get_param("account_balance")

        # RR001: Check Risk:Reward ratio
        rr_item = self._check_rr_ratio(intent, min_rr, cfg)
        if rr_item:
            items.append(rr_item)

        # RR002: Check position risk vs account limits
        if account_balance and intent.total_risk:
            risk_item = self._check_position_risk(
                intent, account_balance, max_risk_pct, cfg
            )
            if risk_item:
                items.append(risk_item)

        # RR003/RR004: Check stop loss distance vs ATR
        if context.atr:
            atr_items = self._check_stop_vs_atr(
                intent, context.atr, min_stop_atr, max_stop_atr, cfg
            )
            items.extend(atr_items)

        # RR005: Check position size vs account
        if account_balance and intent.position_value:
            size_item = self._check_position_size(
                intent, account_balance, max_position_pct, cfg
            )
            if size_item:
                items.append(size_item)

        logger.debug(
            "Risk/reward evaluation complete: %d items found (blockers=%d, critical=%d, warnings=%d)",
            len(items),
            sum(1 for i in items if i.severity == Severity.BLOCKER),
            sum(1 for i in items if i.severity == Severity.CRITICAL),
            sum(1 for i in items if i.severity == Severity.WARNING)
        )
        return items

    def _check_rr_ratio(
        self,
        intent: TradeIntent,
        min_rr: float,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        """Check if R:R ratio meets minimum threshold.

        Args:
            intent: Trade intent
            min_rr: Minimum required R:R ratio
            config: Evaluator config

        Returns:
            EvaluationItem if ratio is below minimum, None otherwise
        """
        rr = intent.risk_reward_ratio

        if rr < min_rr:
            # Determine severity based on how far below threshold
            if rr < 1.0:
                severity = Severity.BLOCKER
                message = (
                    f"Risk/reward ratio of {format_ratio(intent.reward_per_share, intent.risk_per_share)} "
                    f"means you risk more than you stand to gain. "
                    f"Consider widening your target or tightening your stop."
                )
            elif rr < min_rr * 0.75:
                severity = Severity.CRITICAL
                message = (
                    f"Risk/reward ratio of {format_ratio(intent.reward_per_share, intent.risk_per_share)} "
                    f"is significantly below your minimum of {min_rr:.1f}:1. "
                    f"This trade requires a higher win rate to be profitable long-term."
                )
            else:
                severity = Severity.WARNING
                message = (
                    f"Risk/reward ratio of {format_ratio(intent.reward_per_share, intent.risk_per_share)} "
                    f"is below your target of {min_rr:.1f}:1. "
                    f"Consider whether the setup justifies reduced R:R."
                )

            return self.create_item(
                code="RR001",
                severity=config.get_severity("RR001", severity),
                title="Low Risk/Reward Ratio",
                message=message,
                evidence=[
                    Evidence(
                        metric_name="risk_reward_ratio",
                        value=rr,
                        threshold=min_rr,
                        comparison=">=",
                        context={
                            "risk_per_share": intent.risk_per_share,
                            "reward_per_share": intent.reward_per_share,
                        },
                    ),
                ],
                config=config,
            )

        return None

    def _check_position_risk(
        self,
        intent: TradeIntent,
        account_balance: float,
        max_risk_pct: float,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        """Check if position risk exceeds account limits.

        Args:
            intent: Trade intent
            account_balance: Account balance
            max_risk_pct: Maximum risk as percentage of account
            config: Evaluator config

        Returns:
            EvaluationItem if risk exceeds limit, None otherwise
        """
        if not intent.total_risk or account_balance <= 0:
            return None

        risk_pct = (intent.total_risk / account_balance) * 100

        if risk_pct > max_risk_pct:
            # Determine severity
            if risk_pct > max_risk_pct * 2:
                severity = Severity.BLOCKER
            elif risk_pct > max_risk_pct * 1.5:
                severity = Severity.CRITICAL
            else:
                severity = Severity.WARNING

            return self.create_item(
                code="RR002",
                severity=config.get_severity("RR002", severity),
                title="Position Risk Exceeds Limit",
                message=(
                    f"This trade risks {format_percentage(risk_pct)} of your account "
                    f"({format_currency(intent.total_risk)}), exceeding your "
                    f"{format_percentage(max_risk_pct)} limit. "
                    f"Consider reducing position size to stay within risk parameters."
                ),
                evidence=[
                    Evidence(
                        metric_name="risk_percentage",
                        value=risk_pct,
                        threshold=max_risk_pct,
                        comparison="<=",
                        unit="%",
                        context={
                            "total_risk": intent.total_risk,
                            "account_balance": account_balance,
                        },
                    ),
                ],
                config=config,
            )

        return None

    def _check_stop_vs_atr(
        self,
        intent: TradeIntent,
        atr: float,
        min_multiple: float,
        max_multiple: float,
        config: EvaluatorConfig,
    ) -> list[EvaluationItem]:
        """Check stop loss distance relative to ATR.

        Args:
            intent: Trade intent
            atr: Average True Range
            min_multiple: Minimum stop distance in ATR multiples
            max_multiple: Maximum stop distance in ATR multiples
            config: Evaluator config

        Returns:
            List of evaluation items for stop distance issues
        """
        items = []
        stop_distance = intent.risk_per_share

        atr_multiple, atr_evidence = compare_to_atr(stop_distance, atr)

        # RR003: Stop too tight
        if atr_multiple < min_multiple:
            items.append(self.create_item(
                code="RR003",
                severity=config.get_severity("RR003", Severity.WARNING),
                title="Stop Loss May Be Too Tight",
                message=(
                    f"Your stop is {atr_multiple:.2f}x ATR from entry. "
                    f"Stops tighter than {min_multiple:.1f}x ATR may get triggered by "
                    f"normal price fluctuation. Consider whether this stop placement "
                    f"gives the trade room to work."
                ),
                evidence=[
                    Evidence(
                        metric_name="stop_atr_multiple",
                        value=atr_multiple,
                        threshold=min_multiple,
                        comparison=">=",
                        unit="ATR",
                        context={
                            "stop_distance": stop_distance,
                            "atr": atr,
                        },
                    ),
                ],
                config=config,
            ))

        # RR004: Stop too wide
        if atr_multiple > max_multiple:
            items.append(self.create_item(
                code="RR004",
                severity=config.get_severity("RR004", Severity.WARNING),
                title="Stop Loss May Be Too Wide",
                message=(
                    f"Your stop is {atr_multiple:.2f}x ATR from entry. "
                    f"Stops wider than {max_multiple:.1f}x ATR may indicate "
                    f"the entry timing could be refined, or position size should "
                    f"be adjusted to keep dollar risk in check."
                ),
                evidence=[
                    Evidence(
                        metric_name="stop_atr_multiple",
                        value=atr_multiple,
                        threshold=max_multiple,
                        comparison="<=",
                        unit="ATR",
                        context={
                            "stop_distance": stop_distance,
                            "atr": atr,
                        },
                    ),
                ],
                config=config,
            ))

        return items

    def _check_position_size(
        self,
        intent: TradeIntent,
        account_balance: float,
        max_pct: float,
        config: EvaluatorConfig,
    ) -> Optional[EvaluationItem]:
        """Check if position size is too large relative to account.

        Args:
            intent: Trade intent
            account_balance: Account balance
            max_pct: Maximum position as percentage of account
            config: Evaluator config

        Returns:
            EvaluationItem if position too large, None otherwise
        """
        if not intent.position_value or account_balance <= 0:
            return None

        position_pct = (intent.position_value / account_balance) * 100

        if position_pct > max_pct:
            severity = Severity.CRITICAL if position_pct > max_pct * 1.5 else Severity.WARNING

            return self.create_item(
                code="RR005",
                severity=config.get_severity("RR005", severity),
                title="Large Position Size",
                message=(
                    f"This position represents {format_percentage(position_pct)} of your account. "
                    f"Concentrating more than {format_percentage(max_pct)} in a single trade "
                    f"increases portfolio risk. Consider whether this concentration is intentional."
                ),
                evidence=[
                    Evidence(
                        metric_name="position_percentage",
                        value=position_pct,
                        threshold=max_pct,
                        comparison="<=",
                        unit="%",
                        context={
                            "position_value": intent.position_value,
                            "account_balance": account_balance,
                        },
                    ),
                ],
                config=config,
            )

        return None
