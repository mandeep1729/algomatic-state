"""Backward-compatibility shim — checks have moved to src.reviewer.checks.

All imports are re-exported from the new location. Update your imports to
``from src.reviewer.checks import ...`` to avoid deprecation warnings.
"""

import warnings

warnings.warn(
    "src.checks is deprecated, use src.reviewer.checks instead",
    DeprecationWarning,
    stacklevel=2,
)

from src.reviewer.checks.base import BaseChecker, CheckResult
from src.reviewer.checks.risk_sanity import RiskSanityChecker
from src.reviewer.checks.runner import CheckRunner

__all__ = [
    "BaseChecker",
    "CheckResult",
    "CheckRunner",
    "RiskSanityChecker",
]
