"""Risk Sanity Gate — the first must-have behavioral check.

Fires when:
  RS001: No stop-loss specified
  RS002: Risk per trade exceeds account % threshold
  RS003: Risk:Reward ratio below minimum
  RS004: Stop distance smaller than ATR-based volatility floor

All sub-checks use check_type="risk_sanity", check_phase="at_entry".
Passing checks are still recorded (passed=True, severity="info")
to maintain a complete audit trail.

Severity for each sub-check is configurable via ChecksConfig.severity_overrides.
Use the check code as key (e.g. "RS001") for the base severity, and the
code with "_escalated" suffix (e.g. "RS002_escalated") for the escalated
severity that fires under more extreme conditions.
"""

import logging
from typing import Any, Optional

from config.settings import ChecksConfig
from src.reviewer.checks.base import BaseChecker, CheckResult
from src.trade.intent import TradeIntent

logger = logging.getLogger(__name__)

CHECK_TYPE = "risk_sanity"
CHECK_PHASE = "at_entry"

# Default severities per check code.  Escalated variants use '_escalated'.
_DEFAULT_SEVERITIES: dict[str, str] = {
    "RS001": "critical",
    "RS002": "warn",
    "RS002_escalated": "critical",
    "RS003": "warn",
    "RS003_escalated": "critical",
    "RS004": "warn",
}


class RiskSanityChecker(BaseChecker):
    """Evaluates basic risk discipline at trade entry."""

    def __init__(self, config: ChecksConfig):
        self.config = config

    # ------------------------------------------------------------------
    # Severity lookup
    # ------------------------------------------------------------------

    def _severity(self, code: str) -> str:
        """Resolve severity for a check code.

        Checks config.severity_overrides first, then falls back to
        the built-in defaults in _DEFAULT_SEVERITIES.

        Args:
            code: Check code, optionally with '_escalated' suffix

        Returns:
            Severity string (e.g. "warn", "critical")
        """
        overrides = self.config.severity_overrides
        if code in overrides:
            return overrides[code]
        return _DEFAULT_SEVERITIES.get(code, "warn")

    # ------------------------------------------------------------------
    # Runner
    # ------------------------------------------------------------------

    def run(
        self,
        leg: Any,
        intent: Optional[TradeIntent],
        atr: Optional[float],
        account_balance: Optional[float],
    ) -> list[CheckResult]:
        """Run all risk sanity sub-checks.

        Args:
            leg: CampaignLeg model instance
            intent: Linked TradeIntent (None for broker-synced trades)
            atr: ATR value for the symbol/timeframe
            account_balance: Trader's account balance

        Returns:
            List of CheckResult (one per sub-check)
        """
        results: list[CheckResult] = []

        results.append(self._check_no_stop_loss(intent))

        if intent is None:
            logger.debug(
                "Skipping RS002-RS004 for leg_id=%s: no linked intent",
                getattr(leg, "id", "?"),
            )
            return results

        results.append(self._check_risk_pct(intent, account_balance))
        results.append(self._check_rr_ratio(intent))
        results.append(self._check_stop_vs_atr(intent, atr))

        logger.info(
            "Risk sanity checks complete for leg_id=%s: %d passed, %d failed",
            getattr(leg, "id", "?"),
            sum(1 for r in results if r.passed),
            sum(1 for r in results if not r.passed),
        )
        return results

    # ------------------------------------------------------------------
    # RS001 — No stop-loss
    # ------------------------------------------------------------------

    def _check_no_stop_loss(self, intent: Optional[TradeIntent]) -> CheckResult:
        """Check whether a stop-loss is defined."""
        has_stop = intent is not None and intent.stop_loss is not None and intent.stop_loss > 0

        if has_stop:
            return CheckResult(
                check_type=CHECK_TYPE,
                code="RS001",
                severity="info",
                passed=True,
                nudge_text="Stop-loss is defined.",
                check_phase=CHECK_PHASE,
                details={"stop_loss": intent.stop_loss},
            )

        return CheckResult(
            check_type=CHECK_TYPE,
            code="RS001",
            severity=self._severity("RS001"),
            passed=False,
            nudge_text="No stop-loss defined. Every trade needs a predefined exit.",
            check_phase=CHECK_PHASE,
            details={"stop_loss": None},
        )

    # ------------------------------------------------------------------
    # RS002 — Risk % of account
    # ------------------------------------------------------------------

    def _check_risk_pct(
        self,
        intent: TradeIntent,
        account_balance: Optional[float],
    ) -> CheckResult:
        """Check whether risk per trade exceeds the account % threshold."""
        threshold = self.config.max_risk_per_trade_pct
        details: dict[str, Any] = {"threshold_pct": threshold}

        if account_balance is None or account_balance <= 0:
            return CheckResult(
                check_type=CHECK_TYPE,
                code="RS002",
                severity="info",
                passed=True,
                nudge_text="Account balance not available; risk % check skipped.",
                check_phase=CHECK_PHASE,
                details={**details, "reason": "no_account_balance"},
            )

        total_risk = intent.total_risk
        if total_risk is None:
            return CheckResult(
                check_type=CHECK_TYPE,
                code="RS002",
                severity="info",
                passed=True,
                nudge_text="Position size not set; risk % check skipped.",
                check_phase=CHECK_PHASE,
                details={**details, "reason": "no_position_size"},
            )

        risk_pct = (total_risk / account_balance) * 100
        details["risk_pct"] = round(risk_pct, 2)
        details["total_risk"] = round(total_risk, 2)
        details["account_balance"] = round(account_balance, 2)

        if risk_pct <= threshold:
            return CheckResult(
                check_type=CHECK_TYPE,
                code="RS002",
                severity="info",
                passed=True,
                nudge_text=f"Risk is {risk_pct:.1f}% of account, within your {threshold}% limit.",
                check_phase=CHECK_PHASE,
                details=details,
            )

        # >2× threshold → escalated severity, otherwise base severity
        if risk_pct > threshold * 2:
            severity = self._severity("RS002_escalated")
        else:
            severity = self._severity("RS002")

        return CheckResult(
            check_type=CHECK_TYPE,
            code="RS002",
            severity=severity,
            passed=False,
            nudge_text=(
                f"This trade risks {risk_pct:.1f}% of your account, "
                f"exceeding your {threshold}% limit."
            ),
            check_phase=CHECK_PHASE,
            details=details,
        )

    # ------------------------------------------------------------------
    # RS003 — Risk:Reward ratio
    # ------------------------------------------------------------------

    def _check_rr_ratio(self, intent: TradeIntent) -> CheckResult:
        """Check whether risk:reward ratio meets minimum."""
        min_rr = self.config.min_rr_ratio
        actual_rr = intent.risk_reward_ratio
        details: dict[str, Any] = {
            "actual_rr": round(actual_rr, 2),
            "min_rr": min_rr,
        }

        if actual_rr >= min_rr:
            return CheckResult(
                check_type=CHECK_TYPE,
                code="RS003",
                severity="info",
                passed=True,
                nudge_text=f"Risk/reward of {actual_rr:.1f}:1 meets your {min_rr}:1 minimum.",
                check_phase=CHECK_PHASE,
                details=details,
            )

        # R:R < 1.0 → escalated severity, otherwise base severity
        if actual_rr < 1.0:
            severity = self._severity("RS003_escalated")
        else:
            severity = self._severity("RS003")

        return CheckResult(
            check_type=CHECK_TYPE,
            code="RS003",
            severity=severity,
            passed=False,
            nudge_text=(
                f"Risk/reward of {actual_rr:.1f}:1 is below your {min_rr}:1 minimum. "
                f"This setup is statistically fragile."
            ),
            check_phase=CHECK_PHASE,
            details=details,
        )

    # ------------------------------------------------------------------
    # RS004 — Stop distance vs ATR
    # ------------------------------------------------------------------

    def _check_stop_vs_atr(
        self,
        intent: TradeIntent,
        atr: Optional[float],
    ) -> CheckResult:
        """Check whether stop distance is at least min_stop_atr_multiple × ATR."""
        min_multiple = self.config.min_stop_atr_multiple
        stop_distance = intent.risk_per_share
        details: dict[str, Any] = {
            "stop_distance": round(stop_distance, 4),
            "min_atr_multiple": min_multiple,
        }

        if atr is None or atr <= 0:
            return CheckResult(
                check_type=CHECK_TYPE,
                code="RS004",
                severity="info",
                passed=True,
                nudge_text="ATR not available; stop-vs-volatility check skipped.",
                check_phase=CHECK_PHASE,
                details={**details, "reason": "no_atr"},
            )

        atr_multiple = stop_distance / atr
        details["atr"] = round(atr, 4)
        details["atr_multiple"] = round(atr_multiple, 2)

        if atr_multiple >= min_multiple:
            return CheckResult(
                check_type=CHECK_TYPE,
                code="RS004",
                severity="info",
                passed=True,
                nudge_text=(
                    f"Stop is {atr_multiple:.1f}× ATR from entry, "
                    f"above the {min_multiple}× minimum."
                ),
                check_phase=CHECK_PHASE,
                details=details,
            )

        return CheckResult(
            check_type=CHECK_TYPE,
            code="RS004",
            severity=self._severity("RS004"),
            passed=False,
            nudge_text=(
                f"Your stop is {atr_multiple:.1f}× ATR from entry. "
                f"Normal price movement may trigger it."
            ),
            check_phase=CHECK_PHASE,
            details=details,
        )
