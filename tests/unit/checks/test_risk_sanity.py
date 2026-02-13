"""Unit tests for RiskSanityChecker.

Tests all four sub-checks (RS001–RS004) with various scenarios:
- No stop-loss, excessive risk, low R:R, tight stop vs ATR
- Pass and fail cases, edge cases, severity escalation
"""

from unittest.mock import MagicMock

import pytest

from config.settings import ChecksConfig
from src.checks.risk_sanity import RiskSanityChecker
from src.trade.intent import TradeIntent, TradeDirection


@pytest.fixture
def config():
    """Default checks config."""
    return ChecksConfig(
        atr_period=14,
        min_rr_ratio=1.5,
        max_risk_per_trade_pct=2.0,
        min_stop_atr_multiple=0.5,
    )


@pytest.fixture
def checker(config):
    """Checker with default config."""
    return RiskSanityChecker(config)


@pytest.fixture
def mock_leg():
    """Mock campaign leg."""
    leg = MagicMock()
    leg.id = 42
    leg.campaign_id = 10
    return leg


def make_intent(
    entry_price=100.0,
    stop_loss=95.0,
    profit_target=110.0,
    position_size=100,
    direction="long",
):
    """Create a TradeIntent for testing."""
    return TradeIntent(
        user_id=1,
        account_id=1,
        symbol="AAPL",
        direction=TradeDirection(direction),
        timeframe="5Min",
        entry_price=entry_price,
        stop_loss=stop_loss,
        profit_target=profit_target,
        position_size=position_size,
    )


# -----------------------------------------------------------------------
# RS001 — No stop-loss
# -----------------------------------------------------------------------


class TestRS001NoStopLoss:
    """Tests for the no-stop-loss check."""

    def test_no_intent_fails(self, checker, mock_leg):
        """No intent at all → RS001 block."""
        results = checker.run(mock_leg, intent=None, atr=3.5, account_balance=50000)
        rs001 = next(r for r in results if r.code == "RS001")

        assert not rs001.passed
        assert rs001.severity == "block"
        assert "No stop-loss" in rs001.nudge_text

    def test_intent_with_stop_passes(self, checker, mock_leg):
        """Intent with valid stop-loss → RS001 passes."""
        intent = make_intent(stop_loss=95.0)
        results = checker.run(mock_leg, intent=intent, atr=3.5, account_balance=50000)
        rs001 = next(r for r in results if r.code == "RS001")

        assert rs001.passed
        assert rs001.severity == "info"

    def test_no_intent_returns_only_rs001(self, checker, mock_leg):
        """Without an intent, only RS001 fires (RS002-RS004 skipped)."""
        results = checker.run(mock_leg, intent=None, atr=3.5, account_balance=50000)
        assert len(results) == 1
        assert results[0].code == "RS001"

    def test_intent_returns_all_four_checks(self, checker, mock_leg):
        """With an intent, all four sub-checks fire."""
        intent = make_intent()
        results = checker.run(mock_leg, intent=intent, atr=3.5, account_balance=50000)
        codes = {r.code for r in results}
        assert codes == {"RS001", "RS002", "RS003", "RS004"}


# -----------------------------------------------------------------------
# RS002 — Risk % of account
# -----------------------------------------------------------------------


class TestRS002RiskPct:
    """Tests for the risk-as-%-of-account check."""

    def test_risk_within_limit_passes(self, checker, mock_leg):
        """Risk of 1% on a $50k account → passes."""
        # risk_per_share=5, position_size=100, total_risk=500, 500/50000=1%
        intent = make_intent(entry_price=100, stop_loss=95, position_size=100)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs002 = next(r for r in results if r.code == "RS002")

        assert rs002.passed
        assert rs002.severity == "info"
        assert rs002.details["risk_pct"] == 1.0

    def test_risk_exceeds_limit_warns(self, checker, mock_leg):
        """Risk of 3% → warn (above 2% but below 4%)."""
        # risk_per_share=5, position_size=300, total_risk=1500, 1500/50000=3%
        intent = make_intent(entry_price=100, stop_loss=95, position_size=300)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs002 = next(r for r in results if r.code == "RS002")

        assert not rs002.passed
        assert rs002.severity == "warn"

    def test_risk_exceeds_double_limit_blocks(self, checker, mock_leg):
        """Risk of 5% → block (above 2×2% = 4%)."""
        # risk_per_share=5, position_size=500, total_risk=2500, 2500/50000=5%
        intent = make_intent(entry_price=100, stop_loss=95, position_size=500)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs002 = next(r for r in results if r.code == "RS002")

        assert not rs002.passed
        assert rs002.severity == "block"

    def test_no_balance_skips(self, checker, mock_leg):
        """No account balance → passes with skip note."""
        intent = make_intent()
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=None)
        rs002 = next(r for r in results if r.code == "RS002")

        assert rs002.passed
        assert rs002.details.get("reason") == "no_account_balance"

    def test_no_position_size_skips(self, checker, mock_leg):
        """No position size → passes with skip note."""
        intent = make_intent(position_size=None)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs002 = next(r for r in results if r.code == "RS002")

        assert rs002.passed
        assert rs002.details.get("reason") == "no_position_size"

    def test_risk_exactly_at_limit_passes(self, checker, mock_leg):
        """Risk exactly at 2.0% → passes (boundary)."""
        # risk_per_share=5, position_size=200, total_risk=1000, 1000/50000=2%
        intent = make_intent(entry_price=100, stop_loss=95, position_size=200)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs002 = next(r for r in results if r.code == "RS002")

        assert rs002.passed


# -----------------------------------------------------------------------
# RS003 — Risk:Reward ratio
# -----------------------------------------------------------------------


class TestRS003RRRatio:
    """Tests for the risk:reward ratio check."""

    def test_good_rr_passes(self, checker, mock_leg):
        """R:R of 2.0 (above 1.5 min) → passes."""
        # risk=5, reward=10 → R:R=2.0
        intent = make_intent(entry_price=100, stop_loss=95, profit_target=110)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs003 = next(r for r in results if r.code == "RS003")

        assert rs003.passed
        assert rs003.severity == "info"
        assert rs003.details["actual_rr"] == 2.0

    def test_low_rr_warns(self, checker, mock_leg):
        """R:R of 1.2 (below 1.5, above 1.0) → warn."""
        # risk=5, reward=6 → R:R=1.2
        intent = make_intent(entry_price=100, stop_loss=95, profit_target=106)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs003 = next(r for r in results if r.code == "RS003")

        assert not rs003.passed
        assert rs003.severity == "warn"

    def test_rr_below_one_blocks(self, checker, mock_leg):
        """R:R of 0.5 (below 1.0) → block."""
        # risk=10, reward=5 → R:R=0.5
        intent = make_intent(entry_price=100, stop_loss=90, profit_target=105)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs003 = next(r for r in results if r.code == "RS003")

        assert not rs003.passed
        assert rs003.severity == "block"

    def test_rr_exactly_at_minimum_passes(self, checker, mock_leg):
        """R:R of exactly 1.5 → passes (boundary)."""
        # risk=4, reward=6 → R:R=1.5
        intent = make_intent(entry_price=100, stop_loss=96, profit_target=106)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs003 = next(r for r in results if r.code == "RS003")

        assert rs003.passed


# -----------------------------------------------------------------------
# RS004 — Stop distance vs ATR
# -----------------------------------------------------------------------


class TestRS004StopVsATR:
    """Tests for the stop-distance-vs-ATR check."""

    def test_adequate_stop_distance_passes(self, checker, mock_leg):
        """Stop at 1.0× ATR (above 0.5× min) → passes."""
        # risk=5, ATR=5 → multiple=1.0
        intent = make_intent(entry_price=100, stop_loss=95, profit_target=110)
        results = checker.run(mock_leg, intent=intent, atr=5.0, account_balance=50000)
        rs004 = next(r for r in results if r.code == "RS004")

        assert rs004.passed
        assert rs004.severity == "info"
        assert rs004.details["atr_multiple"] == 1.0

    def test_tight_stop_warns(self, checker, mock_leg):
        """Stop at 0.29× ATR (below 0.5× min) → warn."""
        # risk=1, ATR=3.5 → multiple=0.29
        intent = make_intent(entry_price=100, stop_loss=99, profit_target=105)
        results = checker.run(mock_leg, intent=intent, atr=3.5, account_balance=50000)
        rs004 = next(r for r in results if r.code == "RS004")

        assert not rs004.passed
        assert rs004.severity == "warn"
        assert "Normal price movement" in rs004.nudge_text

    def test_no_atr_skips(self, checker, mock_leg):
        """No ATR available → passes with skip note."""
        intent = make_intent()
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs004 = next(r for r in results if r.code == "RS004")

        assert rs004.passed
        assert rs004.details.get("reason") == "no_atr"

    def test_stop_exactly_at_minimum_passes(self, checker, mock_leg):
        """Stop at exactly 0.5× ATR → passes (boundary)."""
        # risk=2.5, ATR=5 → multiple=0.5
        intent = make_intent(entry_price=100, stop_loss=97.5, profit_target=110)
        results = checker.run(mock_leg, intent=intent, atr=5.0, account_balance=50000)
        rs004 = next(r for r in results if r.code == "RS004")

        assert rs004.passed

    def test_short_trade_stop_vs_atr(self, checker, mock_leg):
        """Short trade with tight stop vs ATR → warn."""
        # Short: entry=100, stop=101 → risk=1, ATR=5 → multiple=0.2
        intent = make_intent(
            entry_price=100,
            stop_loss=101,
            profit_target=90,
            direction="short",
        )
        results = checker.run(mock_leg, intent=intent, atr=5.0, account_balance=50000)
        rs004 = next(r for r in results if r.code == "RS004")

        assert not rs004.passed
        assert rs004.severity == "warn"


# -----------------------------------------------------------------------
# Check metadata / structure
# -----------------------------------------------------------------------


class TestCheckMetadata:
    """Tests for check result structure and metadata."""

    def test_all_results_have_check_type(self, checker, mock_leg):
        """All results should have check_type='risk_sanity'."""
        intent = make_intent()
        results = checker.run(mock_leg, intent=intent, atr=3.5, account_balance=50000)

        for r in results:
            assert r.check_type == "risk_sanity"

    def test_all_results_have_at_entry_phase(self, checker, mock_leg):
        """All results should have check_phase='at_entry'."""
        intent = make_intent()
        results = checker.run(mock_leg, intent=intent, atr=3.5, account_balance=50000)

        for r in results:
            assert r.check_phase == "at_entry"

    def test_passing_checks_are_info_severity(self, checker, mock_leg):
        """All passing checks should have severity='info'."""
        # Good trade: R:R=2.0, risk=1%, stop=1.0×ATR
        intent = make_intent(
            entry_price=100, stop_loss=95, profit_target=110, position_size=100,
        )
        results = checker.run(mock_leg, intent=intent, atr=5.0, account_balance=50000)

        for r in results:
            assert r.passed
            assert r.severity == "info"

    def test_custom_config_thresholds(self, mock_leg):
        """Custom config thresholds are respected."""
        strict_config = ChecksConfig(
            min_rr_ratio=3.0,
            max_risk_per_trade_pct=0.5,
            min_stop_atr_multiple=1.0,
        )
        strict_checker = RiskSanityChecker(strict_config)

        # R:R of 2.0 would pass default (1.5) but fails strict (3.0)
        intent = make_intent(entry_price=100, stop_loss=95, profit_target=110)
        results = strict_checker.run(
            mock_leg, intent=intent, atr=5.0, account_balance=50000,
        )
        rs003 = next(r for r in results if r.code == "RS003")
        assert not rs003.passed


# -----------------------------------------------------------------------
# Severity overrides
# -----------------------------------------------------------------------


class TestSeverityOverrides:
    """Tests for configurable severity via severity_overrides."""

    def test_rs001_override_to_danger(self, mock_leg):
        """RS001 severity can be changed from 'block' to 'danger'."""
        cfg = ChecksConfig(severity_overrides={"RS001": "danger"})
        checker = RiskSanityChecker(cfg)

        results = checker.run(mock_leg, intent=None, atr=None, account_balance=None)
        rs001 = results[0]

        assert not rs001.passed
        assert rs001.severity == "danger"

    def test_rs002_base_override(self, mock_leg):
        """RS002 base severity (non-escalated) can be overridden."""
        cfg = ChecksConfig(severity_overrides={"RS002": "danger"})
        checker = RiskSanityChecker(cfg)

        # 3% risk on 2% limit → base (not escalated) failure
        intent = make_intent(entry_price=100, stop_loss=95, position_size=300)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs002 = next(r for r in results if r.code == "RS002")

        assert not rs002.passed
        assert rs002.severity == "danger"

    def test_rs002_escalated_override(self, mock_leg):
        """RS002 escalated severity (>2× threshold) can be overridden."""
        cfg = ChecksConfig(severity_overrides={"RS002_escalated": "danger"})
        checker = RiskSanityChecker(cfg)

        # 5% risk on 2% limit → escalated failure (>2×2%=4%)
        intent = make_intent(entry_price=100, stop_loss=95, position_size=500)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs002 = next(r for r in results if r.code == "RS002")

        assert not rs002.passed
        assert rs002.severity == "danger"

    def test_rs003_base_override(self, mock_leg):
        """RS003 base severity (R:R between 1.0 and min) can be overridden."""
        cfg = ChecksConfig(severity_overrides={"RS003": "danger"})
        checker = RiskSanityChecker(cfg)

        # R:R of 1.2 → base failure (above 1.0 but below 1.5 min)
        intent = make_intent(entry_price=100, stop_loss=95, profit_target=106)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs003 = next(r for r in results if r.code == "RS003")

        assert not rs003.passed
        assert rs003.severity == "danger"

    def test_rs003_escalated_override(self, mock_leg):
        """RS003 escalated severity (R:R < 1.0) can be overridden."""
        cfg = ChecksConfig(severity_overrides={"RS003_escalated": "danger"})
        checker = RiskSanityChecker(cfg)

        # R:R of 0.5 → escalated failure
        intent = make_intent(entry_price=100, stop_loss=90, profit_target=105)
        results = checker.run(mock_leg, intent=intent, atr=None, account_balance=50000)
        rs003 = next(r for r in results if r.code == "RS003")

        assert not rs003.passed
        assert rs003.severity == "danger"

    def test_rs004_override(self, mock_leg):
        """RS004 severity can be overridden."""
        cfg = ChecksConfig(severity_overrides={"RS004": "danger"})
        checker = RiskSanityChecker(cfg)

        # Tight stop: 0.29× ATR
        intent = make_intent(entry_price=100, stop_loss=99, profit_target=105)
        results = checker.run(mock_leg, intent=intent, atr=3.5, account_balance=50000)
        rs004 = next(r for r in results if r.code == "RS004")

        assert not rs004.passed
        assert rs004.severity == "danger"

    def test_passing_checks_unaffected_by_overrides(self, mock_leg):
        """Passing checks always use 'info' regardless of overrides."""
        cfg = ChecksConfig(severity_overrides={
            "RS001": "danger",
            "RS002": "danger",
            "RS003": "danger",
            "RS004": "danger",
        })
        checker = RiskSanityChecker(cfg)

        # All-passing trade
        intent = make_intent(
            entry_price=100, stop_loss=95, profit_target=110, position_size=100,
        )
        results = checker.run(mock_leg, intent=intent, atr=5.0, account_balance=50000)

        for r in results:
            assert r.passed
            assert r.severity == "info"

    def test_multiple_overrides_at_once(self, mock_leg):
        """Multiple codes can be overridden simultaneously."""
        cfg = ChecksConfig(severity_overrides={
            "RS002": "danger",
            "RS003": "danger",
            "RS004": "block",
        })
        checker = RiskSanityChecker(cfg)

        # Bad trade: risk=3% ($1×1500/$50k), R:R=1.2 (risk=5,reward=6), stop=1.43×ATR
        # RS002 fails (3% > 2%), RS003 fails (1.2 < 1.5, base), RS004 fails (1.43× < 0.5×...
        # Actually need tight stop for RS004. Use separate ATR to trigger it.
        # risk_per_share=5, position_size=400 → total_risk=2000, risk_pct=4% (>2%, <4%)
        # R:R: reward=6/risk=5 = 1.2 (base fail, not escalated)
        # stop_distance=5, ATR=15 → multiple=0.33 (<0.5, fails)
        intent = make_intent(
            entry_price=100, stop_loss=95, profit_target=106, position_size=400,
        )
        results = checker.run(mock_leg, intent=intent, atr=15.0, account_balance=50000)

        rs002 = next(r for r in results if r.code == "RS002")
        rs003 = next(r for r in results if r.code == "RS003")
        rs004 = next(r for r in results if r.code == "RS004")

        assert rs002.severity == "danger"
        assert rs003.severity == "danger"
        assert rs004.severity == "block"

    def test_default_severities_when_no_overrides(self, mock_leg):
        """Without overrides, built-in defaults are used."""
        cfg = ChecksConfig()  # no severity_overrides
        checker = RiskSanityChecker(cfg)

        # RS001 fails → default "block"
        results = checker.run(mock_leg, intent=None, atr=None, account_balance=None)
        assert results[0].severity == "block"
