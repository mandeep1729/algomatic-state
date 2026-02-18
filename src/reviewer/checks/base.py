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
        severity: "info" | "warn" | "critical"
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

    Subclasses implement run() to evaluate a trade fill against
    risk/behavioral criteria and return a list of CheckResults.

    Every subclass must define a unique CHECK_NAME class attribute
    (lowercase_with_underscores) that identifies the checker for
    logging, DB persistence, and registry deduplication.
    """

    CHECK_NAME: str  # e.g. "risk_sanity", "entry_quality"

    def __init_subclass__(cls, **kwargs):
        """Validate that concrete subclasses define CHECK_NAME."""
        super().__init_subclass__(**kwargs)
        # Only enforce on concrete (non-abstract) subclasses
        if not getattr(cls, "__abstractmethods__", None):
            if not getattr(cls, "CHECK_NAME", None):
                raise TypeError(
                    f"{cls.__name__} must define a CHECK_NAME class attribute"
                )

    @abstractmethod
    def run(
        self,
        fill: Any,
        intent: Optional[TradeIntent],
        atr: Optional[float],
        account_balance: Optional[float],
        **kwargs,
    ) -> list[CheckResult]:
        """Run checks for a trade fill.

        Args:
            fill: TradeFill model instance
            intent: TradeIntent domain object built from fill data (None if unavailable)
            atr: Current ATR value for the symbol/timeframe
            account_balance: Trader's account balance
            **kwargs: Additional data (e.g. indicator_snapshot, baseline_stats)

        Returns:
            List of CheckResult for each sub-check evaluated
        """
