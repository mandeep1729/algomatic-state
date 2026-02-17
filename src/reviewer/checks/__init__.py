"""Behavioral checks for campaign legs.

Checks run after leg creation and persist CampaignCheck records
that traders can acknowledge and act on. Unlike evaluators (which
provide transient pre-trade feedback), checks create a permanent
audit trail attached to executed trades.
"""

from src.reviewer.checks.base import BaseChecker, CheckResult
from src.reviewer.checks.entry_quality import EntryQualityChecker
from src.reviewer.checks.risk_sanity import RiskSanityChecker
from src.reviewer.checks.runner import CheckRunner

__all__ = [
    "BaseChecker",
    "CheckResult",
    "CheckRunner",
    "EntryQualityChecker",
    "RiskSanityChecker",
]
