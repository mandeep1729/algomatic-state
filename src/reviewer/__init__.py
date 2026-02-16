"""Reviewer Service — event-driven behavioral checks for campaign legs.

Subscribes to review events (leg created, context updated, risk prefs changed,
campaigns populated) and runs behavioral checks asynchronously.

In-process mode (default, MESSAGING_BACKEND=memory): orchestrator starts
on FastAPI startup, checks run synchronously via the in-memory bus.

Standalone mode (MESSAGING_BACKEND=redis): separate reviewer-service container
consumes events via Redis pub/sub.
"""

from src.reviewer.checks.base import BaseChecker, CheckResult
from src.reviewer.checks.risk_sanity import RiskSanityChecker
from src.reviewer.checks.runner import CheckRunner
from src.reviewer.evaluator_runner import EvaluatorRunner
from src.reviewer.orchestrator import ReviewerOrchestrator

__all__ = [
    "BaseChecker",
    "CheckResult",
    "CheckRunner",
    "EvaluatorRunner",
    "ReviewerOrchestrator",
    "RiskSanityChecker",
]
