"""Reviewer Service — event-driven behavioral checks for trade fills.

Subscribes to review events (context updated, risk prefs changed,
campaigns rebuilt, baseline requested) and runs behavioral checks
asynchronously.

In-process mode (default, MESSAGING_BACKEND=memory): orchestrator starts
on FastAPI startup, checks run synchronously via the in-memory bus.

Standalone mode (MESSAGING_BACKEND=redis): separate reviewer-service container
consumes events via Redis pub/sub.
"""

from src.reviewer.api_client import ReviewerApiClient
from src.reviewer.baseline import compute_baseline_stats
from src.reviewer.checks.base import BaseChecker, CheckResult
from src.reviewer.checks.entry_quality import EntryQualityChecker
from src.reviewer.checks.risk_sanity import RiskSanityChecker
from src.reviewer.checks.runner import CheckRunner
from src.reviewer.orchestrator import ReviewerOrchestrator

__all__ = [
    "BaseChecker",
    "CheckResult",
    "CheckRunner",
    "EntryQualityChecker",
    "ReviewerApiClient",
    "ReviewerOrchestrator",
    "RiskSanityChecker",
    "compute_baseline_stats",
]
