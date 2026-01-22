"""Tests for risk manager."""

from datetime import datetime
from unittest.mock import MagicMock
import pytest

from src.execution.orders import Order, OrderSide, OrderType
from src.execution.risk_manager import (
    RiskManager,
    RiskConfig,
    RiskViolation,
    RiskViolationType,
)
from src.execution.client import AccountInfo, PositionInfo


class TestRiskConfig:
    """Tests for RiskConfig."""

    def test_default_values(self):
        config = RiskConfig()
        assert config.max_position_value == 50000.0
        assert config.max_position_pct == 0.20
        assert config.max_daily_loss_pct == 0.02
        assert config.max_drawdown_pct == 0.10
        assert config.enabled is True

    def test_custom_values(self):
        config = RiskConfig(
            max_position_value=25000.0,
            max_position_pct=0.10,
            max_daily_loss_pct=0.01,
        )
        assert config.max_position_value == 25000.0
        assert config.max_position_pct == 0.10
        assert config.max_daily_loss_pct == 0.01


class TestRiskViolation:
    """Tests for RiskViolation."""

    def test_create_violation(self):
        violation = RiskViolation(
            violation_type=RiskViolationType.POSITION_SIZE,
            message="Position too large",
            current_value=60000.0,
            limit_value=50000.0,
        )
        assert violation.violation_type == RiskViolationType.POSITION_SIZE
        assert "Position too large" in str(violation)

    def test_violation_with_order(self, sample_order):
        violation = RiskViolation(
            violation_type=RiskViolationType.ORDER_SIZE,
            message="Order too large",
            current_value=30000.0,
            limit_value=25000.0,
            order=sample_order,
        )
        assert violation.order == sample_order


class TestRiskManager:
    """Tests for RiskManager."""

    @pytest.fixture
    def risk_manager(self, mock_alpaca_client):
        """Create a risk manager with mock client."""
        config = RiskConfig(
            max_position_value=20000.0,
            max_position_pct=0.15,
            max_order_value=10000.0,
            max_order_pct=0.10,
            max_daily_loss_pct=0.02,
            max_drawdown_pct=0.10,
            max_symbols=5,
            min_buying_power_pct=0.10,
        )
        return RiskManager(mock_alpaca_client, config)

    def test_initialization(self, risk_manager):
        assert risk_manager.config.max_position_value == 20000.0
        assert risk_manager.peak_equity == 0.0

    def test_initialize_from_account(self, risk_manager, sample_account_info, mock_alpaca_client):
        mock_alpaca_client.get_account.return_value = sample_account_info
        risk_manager.initialize()
        assert risk_manager.peak_equity == sample_account_info.equity
        assert risk_manager.daily_starting_equity == sample_account_info.equity

    def test_check_order_passes_valid_order(
        self, risk_manager, sample_order, sample_account_info, sample_positions
    ):
        # Small order should pass when there are existing positions
        small_order = Order(
            symbol="GOOGL",  # Different symbol than existing positions
            side=OrderSide.BUY,
            quantity=10.0,
        )
        violations = risk_manager.check_order(
            small_order,
            price=150.0,
            account=sample_account_info,
            positions=sample_positions,  # Has existing positions so concentration is not 100%
        )
        assert len(violations) == 0

    def test_check_order_fails_trading_blocked(
        self, risk_manager, sample_order, blocked_account_info
    ):
        violations = risk_manager.check_order(
            sample_order,
            price=150.0,
            account=blocked_account_info,
            positions=[],
        )
        assert len(violations) == 1
        assert violations[0].violation_type == RiskViolationType.TRADING_BLOCKED

    def test_check_order_fails_insufficient_buying_power(self, risk_manager, sample_account_info):
        # Create order larger than buying power
        large_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1000.0,  # 1000 * 150 = 150,000 > buying power
        )
        violations = risk_manager.check_order(
            large_order,
            price=150.0,
            account=sample_account_info,
            positions=[],
        )
        # Should have buying power violation
        buying_power_violations = [
            v for v in violations
            if v.violation_type == RiskViolationType.BUYING_POWER
        ]
        assert len(buying_power_violations) >= 1

    def test_check_order_fails_order_size_limit(self, risk_manager, sample_account_info):
        # Order value > max_order_value (10000)
        large_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,  # 100 * 150 = 15,000 > 10,000
        )
        violations = risk_manager.check_order(
            large_order,
            price=150.0,
            account=sample_account_info,
            positions=[],
        )
        order_size_violations = [
            v for v in violations
            if v.violation_type == RiskViolationType.ORDER_SIZE
        ]
        assert len(order_size_violations) >= 1

    def test_check_order_fails_position_limit(self, risk_manager, sample_account_info, sample_positions):
        # Existing AAPL position + new order exceeds limit
        large_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=50.0,  # Would bring position to 150 * 150 = 22,500 > 20,000
        )
        violations = risk_manager.check_order(
            large_order,
            price=150.0,
            account=sample_account_info,
            positions=sample_positions,
        )
        position_violations = [
            v for v in violations
            if v.violation_type == RiskViolationType.POSITION_SIZE
        ]
        assert len(position_violations) >= 1

    def test_check_order_fails_symbol_limit(self, risk_manager, sample_account_info):
        # Create positions at symbol limit
        positions = [
            PositionInfo(symbol=f"SYM{i}", quantity=10, market_value=1000,
                        avg_entry_price=100, unrealized_pl=0, unrealized_pl_pct=0,
                        current_price=100, side="long")
            for i in range(5)  # 5 symbols = max_symbols
        ]

        # Try to add a new symbol
        new_order = Order(
            symbol="NEW",
            side=OrderSide.BUY,
            quantity=10.0,
        )
        violations = risk_manager.check_order(
            new_order,
            price=100.0,
            account=sample_account_info,
            positions=positions,
        )
        symbol_violations = [
            v for v in violations
            if v.violation_type == RiskViolationType.SYMBOL_LIMIT
        ]
        assert len(symbol_violations) == 1

    def test_check_order_skips_symbol_check_for_sells(self, risk_manager, sample_account_info):
        # Create positions at symbol limit
        positions = [
            PositionInfo(symbol=f"SYM{i}", quantity=10, market_value=1000,
                        avg_entry_price=100, unrealized_pl=0, unrealized_pl_pct=0,
                        current_price=100, side="long")
            for i in range(5)
        ]

        # Sell order for existing position should pass symbol check
        sell_order = Order(
            symbol="SYM0",
            side=OrderSide.SELL,
            quantity=5.0,
        )
        violations = risk_manager.check_order(
            sell_order,
            price=100.0,
            account=sample_account_info,
            positions=positions,
        )
        symbol_violations = [
            v for v in violations
            if v.violation_type == RiskViolationType.SYMBOL_LIMIT
        ]
        assert len(symbol_violations) == 0

    def test_disabled_risk_manager(self, mock_alpaca_client, sample_order, sample_account_info):
        config = RiskConfig(enabled=False)
        risk_manager = RiskManager(mock_alpaca_client, config)

        violations = risk_manager.check_order(
            sample_order,
            price=150.0,
            account=sample_account_info,
            positions=[],
        )
        assert len(violations) == 0

    def test_is_trading_allowed_normal(self, risk_manager, sample_account_info, mock_alpaca_client):
        mock_alpaca_client.get_account.return_value = sample_account_info
        risk_manager.initialize()

        allowed, reason = risk_manager.is_trading_allowed(sample_account_info)
        assert allowed is True

    def test_is_trading_allowed_blocked(self, risk_manager, blocked_account_info):
        allowed, reason = risk_manager.is_trading_allowed(blocked_account_info)
        assert allowed is False
        assert "blocked" in reason.lower()

    def test_get_available_capacity(self, risk_manager, sample_account_info, mock_alpaca_client):
        mock_alpaca_client.get_account.return_value = sample_account_info
        mock_alpaca_client.get_positions.return_value = []

        capacity = risk_manager.get_available_capacity(
            "AAPL",
            price=150.0,
            account=sample_account_info,
            positions=[],
        )
        # Should be limited by one of the constraints
        assert capacity > 0
        assert capacity <= risk_manager.config.max_order_value

    def test_get_risk_summary(self, risk_manager, sample_account_info, sample_positions, mock_alpaca_client):
        mock_alpaca_client.get_account.return_value = sample_account_info
        risk_manager.initialize()

        summary = risk_manager.get_risk_summary(sample_account_info, sample_positions)

        assert "equity" in summary
        assert "buying_power" in summary
        assert "daily_pnl" in summary
        assert "position_count" in summary
        assert "limits" in summary

    def test_daily_loss_check(self, risk_manager, mock_alpaca_client):
        # Initialize with starting equity
        starting_equity = 100000.0
        account = AccountInfo(
            account_id="test",
            buying_power=100000.0,
            cash=50000.0,
            portfolio_value=100000.0,
            equity=starting_equity,
            last_equity=100000.0,
            long_market_value=50000.0,
            short_market_value=0.0,
            initial_margin=25000.0,
            maintenance_margin=12500.0,
            daytrade_count=0,
            pattern_day_trader=False,
            trading_blocked=False,
            transfers_blocked=False,
            account_blocked=False,
        )
        mock_alpaca_client.get_account.return_value = account
        risk_manager.initialize()

        # Simulate a loss > 2%
        loss_account = AccountInfo(
            account_id="test",
            buying_power=97000.0,
            cash=47000.0,
            portfolio_value=97000.0,
            equity=97000.0,  # 3% loss
            last_equity=100000.0,
            long_market_value=50000.0,
            short_market_value=0.0,
            initial_margin=25000.0,
            maintenance_margin=12500.0,
            daytrade_count=0,
            pattern_day_trader=False,
            trading_blocked=False,
            transfers_blocked=False,
            account_blocked=False,
        )

        allowed, reason = risk_manager.is_trading_allowed(loss_account)
        assert allowed is False
        assert "loss" in reason.lower()

    def test_max_drawdown_check(self, risk_manager, mock_alpaca_client):
        # Initialize with peak equity
        account = AccountInfo(
            account_id="test",
            buying_power=100000.0,
            cash=50000.0,
            portfolio_value=100000.0,
            equity=100000.0,
            last_equity=100000.0,
            long_market_value=50000.0,
            short_market_value=0.0,
            initial_margin=25000.0,
            maintenance_margin=12500.0,
            daytrade_count=0,
            pattern_day_trader=False,
            trading_blocked=False,
            transfers_blocked=False,
            account_blocked=False,
        )
        mock_alpaca_client.get_account.return_value = account
        risk_manager.initialize()

        # Manually set peak equity higher and daily starting equity to match current
        # This simulates a multi-day drawdown where today started at current level
        risk_manager._peak_equity = 100000.0
        risk_manager._daily_starting_equity = 88000.0  # Today started at this level (no daily loss)

        # Simulate drawdown > 10% but no daily loss
        drawdown_account = AccountInfo(
            account_id="test",
            buying_power=88000.0,
            cash=44000.0,
            portfolio_value=88000.0,
            equity=88000.0,  # 12% drawdown from peak
            last_equity=88000.0,
            long_market_value=44000.0,
            short_market_value=0.0,
            initial_margin=22000.0,
            maintenance_margin=11000.0,
            daytrade_count=0,
            pattern_day_trader=False,
            trading_blocked=False,
            transfers_blocked=False,
            account_blocked=False,
        )

        allowed, reason = risk_manager.is_trading_allowed(drawdown_account)
        assert allowed is False
        assert "drawdown" in reason.lower()
