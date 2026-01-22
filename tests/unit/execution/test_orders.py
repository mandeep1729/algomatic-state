"""Tests for order data types."""

from datetime import datetime
import pytest

from src.execution.orders import (
    Order,
    OrderSide,
    OrderType,
    OrderStatus,
    OrderTimeInForce,
)


class TestOrderSide:
    """Tests for OrderSide enum."""

    def test_buy_value(self):
        assert OrderSide.BUY.value == "buy"
        assert str(OrderSide.BUY) == "buy"

    def test_sell_value(self):
        assert OrderSide.SELL.value == "sell"
        assert str(OrderSide.SELL) == "sell"


class TestOrderType:
    """Tests for OrderType enum."""

    def test_market_value(self):
        assert OrderType.MARKET.value == "market"

    def test_limit_value(self):
        assert OrderType.LIMIT.value == "limit"

    def test_stop_value(self):
        assert OrderType.STOP.value == "stop"

    def test_stop_limit_value(self):
        assert OrderType.STOP_LIMIT.value == "stop_limit"


class TestOrderStatus:
    """Tests for OrderStatus enum."""

    def test_terminal_states(self):
        assert OrderStatus.FILLED.is_terminal
        assert OrderStatus.CANCELLED.is_terminal
        assert OrderStatus.REJECTED.is_terminal
        assert OrderStatus.EXPIRED.is_terminal
        assert OrderStatus.FAILED.is_terminal

    def test_active_states(self):
        assert OrderStatus.PENDING.is_active
        assert OrderStatus.SUBMITTED.is_active
        assert OrderStatus.ACCEPTED.is_active
        assert OrderStatus.PARTIALLY_FILLED.is_active

    def test_filled_not_active(self):
        assert not OrderStatus.FILLED.is_active


class TestOrder:
    """Tests for Order dataclass."""

    def test_create_market_order(self):
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
        )
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.quantity == 100.0
        assert order.order_type == OrderType.MARKET
        assert order.status == OrderStatus.PENDING

    def test_create_limit_order(self):
        order = Order(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=50.0,
            order_type=OrderType.LIMIT,
            limit_price=150.0,
        )
        assert order.order_type == OrderType.LIMIT
        assert order.limit_price == 150.0

    def test_limit_order_requires_price(self):
        with pytest.raises(ValueError, match="Limit price required"):
            Order(
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=100.0,
                order_type=OrderType.LIMIT,
            )

    def test_stop_order_requires_stop_price(self):
        with pytest.raises(ValueError, match="Stop price required"):
            Order(
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=100.0,
                order_type=OrderType.STOP,
            )

    def test_stop_limit_requires_both_prices(self):
        with pytest.raises(ValueError, match="Stop price required"):
            Order(
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=100.0,
                order_type=OrderType.STOP_LIMIT,
                limit_price=150.0,
            )

    def test_quantity_must_be_positive(self):
        with pytest.raises(ValueError, match="Quantity must be positive"):
            Order(
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=0.0,
            )

    def test_is_buy_property(self):
        order = Order(symbol="AAPL", side=OrderSide.BUY, quantity=100.0)
        assert order.is_buy
        assert not order.is_sell

    def test_is_sell_property(self):
        order = Order(symbol="AAPL", side=OrderSide.SELL, quantity=100.0)
        assert order.is_sell
        assert not order.is_buy

    def test_remaining_quantity(self):
        order = Order(symbol="AAPL", side=OrderSide.BUY, quantity=100.0)
        assert order.remaining_quantity == 100.0

        order.filled_quantity = 30.0
        assert order.remaining_quantity == 70.0

    def test_is_filled_property(self, filled_order):
        assert filled_order.is_filled

    def test_is_active_property(self, sample_order):
        assert sample_order.is_active

    def test_notional_value(self, sample_limit_order):
        assert sample_limit_order.notional_value == 100.0 * 150.0

    def test_update_fill(self):
        order = Order(symbol="AAPL", side=OrderSide.BUY, quantity=100.0)
        order.broker_order_id = "broker_123"

        order.update_fill(50.0, 150.0)
        assert order.filled_quantity == 50.0
        assert order.filled_avg_price == 150.0
        assert order.status == OrderStatus.PARTIALLY_FILLED

        order.update_fill(100.0, 150.25)
        assert order.filled_quantity == 100.0
        assert order.status == OrderStatus.FILLED
        assert order.filled_at is not None

    def test_to_dict(self, sample_order):
        d = sample_order.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["side"] == "buy"
        assert d["quantity"] == 100.0
        assert d["order_type"] == "market"
        assert d["status"] == "pending"

    def test_from_dict(self, sample_order):
        d = sample_order.to_dict()
        restored = Order.from_dict(d)
        assert restored.symbol == sample_order.symbol
        assert restored.side == sample_order.side
        assert restored.quantity == sample_order.quantity
        assert restored.order_type == sample_order.order_type

    def test_market_order_factory(self):
        order = Order.market_order(
            symbol="MSFT",
            side=OrderSide.BUY,
            quantity=50.0,
        )
        assert order.symbol == "MSFT"
        assert order.order_type == OrderType.MARKET
        assert order.quantity == 50.0

    def test_limit_order_factory(self):
        order = Order.limit_order(
            symbol="GOOGL",
            side=OrderSide.SELL,
            quantity=25.0,
            limit_price=140.0,
        )
        assert order.symbol == "GOOGL"
        assert order.order_type == OrderType.LIMIT
        assert order.limit_price == 140.0


class TestOrderTimeInForce:
    """Tests for OrderTimeInForce enum."""

    def test_day_value(self):
        assert OrderTimeInForce.DAY.value == "day"

    def test_gtc_value(self):
        assert OrderTimeInForce.GTC.value == "gtc"

    def test_ioc_value(self):
        assert OrderTimeInForce.IOC.value == "ioc"
