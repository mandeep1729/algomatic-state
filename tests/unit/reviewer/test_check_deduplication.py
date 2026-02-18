"""Unit tests for check deduplication in CheckRunner.

Verifies that:
1. Checks already recorded for a decision context are skipped
2. New checks run normally when no prior records exist
3. The same check runs independently for different contexts/accounts
4. All checks run when dedup query fails (fail-open)
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from config.settings import ChecksConfig
from src.reviewer.checks.base import BaseChecker, CheckResult
from src.reviewer.checks.runner import CheckRunner
from src.trade.intent import TradeDirection, TradeIntent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StubCheckerA(BaseChecker):
    """Stub checker for testing."""

    CHECK_NAME = "stub_a"

    def run(self, fill, intent, atr, account_balance, **kwargs):
        return [
            CheckResult(
                check_type="stub",
                code="SA001",
                severity="info",
                passed=True,
                nudge_text="Stub A passed.",
                check_phase="at_entry",
            )
        ]


class StubCheckerB(BaseChecker):
    """Second stub checker for testing."""

    CHECK_NAME = "stub_b"

    def run(self, fill, intent, atr, account_balance, **kwargs):
        return [
            CheckResult(
                check_type="stub",
                code="SB001",
                severity="warn",
                passed=False,
                nudge_text="Stub B failed.",
                check_phase="at_entry",
            )
        ]


def _make_mock_dc(dc_id=10, account_id=1):
    """Create a mock DecisionContext."""
    dc = MagicMock()
    dc.id = dc_id
    dc.account_id = account_id
    dc.exit_intent = None
    return dc


def _make_mock_fill(fill_id=42, price=100.0, side="buy", symbol="AAPL"):
    """Create a mock TradeFill."""
    fill = MagicMock()
    fill.id = fill_id
    fill.price = price
    fill.side = side
    fill.symbol = symbol
    fill.quantity = 100
    fill.decision_context = None
    return fill


@pytest.fixture
def config():
    """Default checks config."""
    return ChecksConfig()


@pytest.fixture
def mock_session():
    """Mock SQLAlchemy session."""
    session = MagicMock()
    return session


# ---------------------------------------------------------------------------
# Test: checks skipped when already recorded
# ---------------------------------------------------------------------------


class TestChecksSkippedWhenAlreadyRecorded:
    """Verify that checkers are not re-run when their CHECK_NAME is already in the DB."""

    def test_all_checks_skipped(self, config, mock_session):
        """When all check names exist in DB, no checkers run and no records persist."""
        runner = CheckRunner(mock_session, config)
        runner.checkers = [StubCheckerA(), StubCheckerB()]

        dc = _make_mock_dc()
        fill = _make_mock_fill()

        with patch.object(
            runner, "_get_existing_check_names", return_value={"stub_a", "stub_b"},
        ):
            result = runner.run_checks(dc, fill)

        assert result == []
        mock_session.add.assert_not_called()
        mock_session.flush.assert_not_called()

    def test_partial_skip(self, config, mock_session):
        """When only one check name exists, the other still runs."""
        runner = CheckRunner(mock_session, config)
        runner.checkers = [StubCheckerA(), StubCheckerB()]

        dc = _make_mock_dc()
        fill = _make_mock_fill()

        with patch.object(
            runner, "_get_existing_check_names", return_value={"stub_a"},
        ):
            result = runner.run_checks(dc, fill)

        # Only StubCheckerB should have run (produces code SB001)
        assert len(result) == 1
        assert result[0].check_name == "SB001"


# ---------------------------------------------------------------------------
# Test: new checks run normally
# ---------------------------------------------------------------------------


class TestNewChecksRunNormally:
    """Verify that all checks run when no prior records exist."""

    def test_all_checks_run_when_no_existing(self, config, mock_session):
        """When no check names exist in DB, all checkers run."""
        runner = CheckRunner(mock_session, config)
        runner.checkers = [StubCheckerA(), StubCheckerB()]

        dc = _make_mock_dc()
        fill = _make_mock_fill()

        with patch.object(
            runner, "_get_existing_check_names", return_value=set(),
        ):
            result = runner.run_checks(dc, fill)

        # Both checkers produce one result each
        assert len(result) == 2
        codes = {r.check_name for r in result}
        assert codes == {"SA001", "SB001"}

    def test_records_are_persisted(self, config, mock_session):
        """Check records are added to the session and flushed."""
        runner = CheckRunner(mock_session, config)
        runner.checkers = [StubCheckerA()]

        dc = _make_mock_dc()
        fill = _make_mock_fill()

        with patch.object(
            runner, "_get_existing_check_names", return_value=set(),
        ):
            result = runner.run_checks(dc, fill)

        assert len(result) == 1
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()


# ---------------------------------------------------------------------------
# Test: same check runs for different contexts / accounts
# ---------------------------------------------------------------------------


class TestDifferentContextsAndAccounts:
    """Verify that dedup is scoped to (account_id, decision_context_id)."""

    def test_same_check_different_context(self, config, mock_session):
        """A check already run for dc_id=10 does not block dc_id=20."""
        runner = CheckRunner(mock_session, config)
        runner.checkers = [StubCheckerA()]

        dc_first = _make_mock_dc(dc_id=10, account_id=1)
        dc_second = _make_mock_dc(dc_id=20, account_id=1)
        fill = _make_mock_fill()

        # First context: stub_a already exists
        with patch.object(
            runner, "_get_existing_check_names", return_value={"stub_a"},
        ):
            result_first = runner.run_checks(dc_first, fill)

        # Second context: no existing checks
        with patch.object(
            runner, "_get_existing_check_names", return_value=set(),
        ):
            result_second = runner.run_checks(dc_second, fill)

        assert result_first == []
        assert len(result_second) == 1
        assert result_second[0].check_name == "SA001"

    def test_same_check_different_account(self, config, mock_session):
        """A check already run for account_id=1 does not block account_id=2."""
        runner = CheckRunner(mock_session, config)
        runner.checkers = [StubCheckerA()]

        dc_user1 = _make_mock_dc(dc_id=10, account_id=1)
        dc_user2 = _make_mock_dc(dc_id=10, account_id=2)
        fill = _make_mock_fill()

        # User 1: stub_a already exists
        with patch.object(
            runner, "_get_existing_check_names", return_value={"stub_a"},
        ):
            result_user1 = runner.run_checks(dc_user1, fill)

        # User 2: no existing checks
        with patch.object(
            runner, "_get_existing_check_names", return_value=set(),
        ):
            result_user2 = runner.run_checks(dc_user2, fill)

        assert result_user1 == []
        assert len(result_user2) == 1


# ---------------------------------------------------------------------------
# Test: fail-open behavior
# ---------------------------------------------------------------------------


class TestFailOpenDeduplication:
    """Verify that if the dedup query fails, all checks still run."""

    def test_all_checks_run_on_query_failure(self, config, mock_session):
        """When _get_existing_check_names raises, all checkers run anyway."""
        runner = CheckRunner(mock_session, config)
        runner.checkers = [StubCheckerA(), StubCheckerB()]

        dc = _make_mock_dc()
        fill = _make_mock_fill()

        # Simulate the BrokerRepository call raising
        with patch(
            "src.reviewer.checks.runner.BrokerRepository",
        ) as mock_repo_cls:
            mock_repo_cls.return_value.get_existing_check_names.side_effect = (
                RuntimeError("DB query failed")
            )
            result = runner.run_checks(dc, fill)

        # Both checkers should have run
        assert len(result) == 2
        codes = {r.check_name for r in result}
        assert codes == {"SA001", "SB001"}


# ---------------------------------------------------------------------------
# Test: get_existing_check_names delegates to BrokerRepository
# ---------------------------------------------------------------------------


class TestGetExistingCheckNames:
    """Verify _get_existing_check_names delegates correctly."""

    def test_delegates_to_broker_repository(self, config, mock_session):
        """Calls BrokerRepository.get_existing_check_names with correct args."""
        runner = CheckRunner(mock_session, config)

        dc = _make_mock_dc(dc_id=10, account_id=1)

        with patch(
            "src.reviewer.checks.runner.BrokerRepository",
        ) as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_existing_check_names.return_value = {"risk_sanity"}
            mock_repo_cls.return_value = mock_repo

            result = runner._get_existing_check_names(dc)

        mock_repo_cls.assert_called_once_with(mock_session)
        mock_repo.get_existing_check_names.assert_called_once_with(1, 10)
        assert result == {"risk_sanity"}

    def test_returns_empty_set_on_error(self, config, mock_session):
        """Returns empty set when BrokerRepository raises."""
        runner = CheckRunner(mock_session, config)

        dc = _make_mock_dc(dc_id=10, account_id=1)

        with patch(
            "src.reviewer.checks.runner.BrokerRepository",
        ) as mock_repo_cls:
            mock_repo_cls.return_value.get_existing_check_names.side_effect = (
                RuntimeError("DB error")
            )
            result = runner._get_existing_check_names(dc)

        assert result == set()
