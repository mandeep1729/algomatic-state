"""Base checker interface and result dataclass.

Defines the contract that all behavioral checkers must implement.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from src.trade.intent import TradeIntent

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a single behavioral check.

    Each checker may produce multiple CheckResults (one per sub-check).
    These are converted to CampaignCheck DB records by the CheckRunner.

    Attributes:
        check_type: Category of check (e.g. "risk_sanity")
        code: Unique code for this sub-check (e.g. "RS001")
        severity: "info" | "warn" | "block"
        passed: Whether the check passed
        details: Structured metrics for JSONB storage
        nudge_text: Human-readable message for the trader
        check_phase: When this check applies (e.g. "at_entry")
    """

    check_type: str
    code: str
    severity: str
    passed: bool
    nudge_text: str
    check_phase: str
    details: dict[str, Any] = field(default_factory=dict)


class BaseChecker(ABC):
    """Abstract base class for behavioral checkers.

    Subclasses implement run() to evaluate a campaign leg against
    risk/behavioral criteria and return a list of CheckResults.
    """

    @abstractmethod
    def run(
        self,
        leg: Any,
        intent: Optional[TradeIntent],
        atr: Optional[float],
        account_balance: Optional[float],
    ) -> list[CheckResult]:
        """Run checks for a campaign leg.

        Args:
            leg: CampaignLeg model instance
            intent: Linked TradeIntent domain object (None if broker-synced)
            atr: Current ATR value for the symbol/timeframe
            account_balance: Trader's account balance

        Returns:
            List of CheckResult for each sub-check evaluated
        """
