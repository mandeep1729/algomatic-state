"""Test fixtures for execution module tests."""

from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from src.execution.orders import Order, OrderSide, OrderType, OrderStatus, OrderTimeInForce
from src.execution.client import AccountInfo, PositionInfo
from src.execution.order_manager import Signal, SignalDirection, SignalMetadata


@pytest.fixture
def sample_order():
    """Create a sample market order."""
    return Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100.0,
        order_type=OrderType.MARKET,
        time_in_force=OrderTimeInForce.DAY,
        client_order_id="test_order_001",
    )


@pytest.fixture
def sample_limit_order():
    """Create a sample limit order."""
    return Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100.0,
        order_type=OrderType.LIMIT,
        limit_price=150.0,
        time_in_force=OrderTimeInForce.DAY,
        client_order_id="test_limit_001",
    )


@pytest.fixture
def sample_sell_order():
    """Create a sample sell order."""
    return Order(
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=50.0,
        order_type=OrderType.MARKET,
        time_in_force=OrderTimeInForce.DAY,
        client_order_id="test_sell_001",
    )


@pytest.fixture
def filled_order():
    """Create a filled order."""
    order = Order(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100.0,
        order_type=OrderType.MARKET,
        client_order_id="test_filled_001",
        broker_order_id="broker_123",
        status=OrderStatus.FILLED,
        filled_quantity=100.0,
        filled_avg_price=150.50,
        filled_at=datetime.now(),
    )
    return order


@pytest.fixture
def sample_account_info():
    """Create sample account info."""
    return AccountInfo(
        account_id="test_account_123",
        buying_power=100000.0,
        cash=50000.0,
        portfolio_value=150000.0,
        equity=150000.0,
        last_equity=149000.0,
        long_market_value=100000.0,
        short_market_value=0.0,
        initial_margin=50000.0,
        maintenance_margin=25000.0,
        daytrade_count=0,
        pattern_day_trader=False,
        trading_blocked=False,
        transfers_blocked=False,
        account_blocked=False,
    )


@pytest.fixture
def blocked_account_info():
    """Create blocked account info."""
    return AccountInfo(
        account_id="blocked_account",
        buying_power=0.0,
        cash=50000.0,
        portfolio_value=150000.0,
        equity=150000.0,
        last_equity=149000.0,
        long_market_value=100000.0,
        short_market_value=0.0,
        initial_margin=50000.0,
        maintenance_margin=25000.0,
        daytrade_count=0,
        pattern_day_trader=False,
        trading_blocked=True,
        transfers_blocked=False,
        account_blocked=False,
    )


@pytest.fixture
def sample_positions():
    """Create sample positions."""
    return [
        PositionInfo(
            symbol="AAPL",
            quantity=100.0,
            market_value=15000.0,
            avg_entry_price=145.0,
            unrealized_pl=500.0,
            unrealized_pl_pct=3.45,
            current_price=150.0,
            side="long",
        ),
        PositionInfo(
            symbol="MSFT",
            quantity=50.0,
            market_value=18000.0,
            avg_entry_price=350.0,
            unrealized_pl=1000.0,
            unrealized_pl_pct=5.88,
            current_price=360.0,
            side="long",
        ),
    ]


@pytest.fixture
def sample_long_signal():
    """Create a sample long signal."""
    return Signal(
        timestamp=datetime.now(),
        symbol="AAPL",
        direction=SignalDirection.LONG,
        strength=0.8,
        size=10000.0,
        metadata=SignalMetadata(
            regime_label=1,
            regime_sharpe=1.5,
            momentum_value=0.002,
        ),
    )


@pytest.fixture
def sample_short_signal():
    """Create a sample short signal."""
    return Signal(
        timestamp=datetime.now(),
        symbol="AAPL",
        direction=SignalDirection.SHORT,
        strength=0.6,
        size=5000.0,
        metadata=SignalMetadata(
            regime_label=2,
            regime_sharpe=0.5,
            momentum_value=-0.002,
        ),
    )


@pytest.fixture
def sample_flat_signal():
    """Create a sample flat (exit) signal."""
    return Signal(
        timestamp=datetime.now(),
        symbol="AAPL",
        direction=SignalDirection.FLAT,
        strength=1.0,
        size=0.0,
    )


@pytest.fixture
def mock_alpaca_client():
    """Create a mock Alpaca client."""
    client = MagicMock()

    # Mock account
    client.get_account.return_value = AccountInfo(
        account_id="mock_account",
        buying_power=100000.0,
        cash=50000.0,
        portfolio_value=150000.0,
        equity=150000.0,
        last_equity=149000.0,
        long_market_value=100000.0,
        short_market_value=0.0,
        initial_margin=50000.0,
        maintenance_margin=25000.0,
        daytrade_count=0,
        pattern_day_trader=False,
        trading_blocked=False,
        transfers_blocked=False,
        account_blocked=False,
    )

    # Mock positions
    client.get_positions.return_value = []

    # Mock market hours
    client.is_market_open.return_value = True

    return client
