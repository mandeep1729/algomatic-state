"""Tests for order manager."""

from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from src.execution.orders import Order, OrderSide, OrderType, OrderStatus, OrderTimeInForce
from src.execution.order_manager import OrderManager
from src.strategy.signals import Signal, SignalDirection, SignalMetadata


class TestOrderManager:
    """Tests for OrderManager."""

    @pytest.fixture
    def order_manager(self, mock_alpaca_client):
        """Create an order manager with mock client."""
        return OrderManager(mock_alpaca_client)

    def test_initialization(self, order_manager):
        assert len(order_manager.pending_orders) == 0
        assert len(order_manager.order_history) == 0

    def test_generate_client_order_id(self, order_manager):
        id1 = order_manager.generate_client_order_id()
        id2 = order_manager.generate_client_order_id()
        assert id1.startswith("algo_")
        assert id2.startswith("algo_")
        assert id1 != id2

    def test_signal_to_order_long(self, order_manager, sample_long_signal):
        order = order_manager.signal_to_order(
            sample_long_signal,
            current_price=150.0,
        )

        assert order is not None
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.quantity == int(10000.0 / 150.0)  # size / price
        assert order.order_type == OrderType.MARKET

    def test_signal_to_order_short(self, order_manager, sample_short_signal):
        order = order_manager.signal_to_order(
            sample_short_signal,
            current_price=150.0,
        )

        assert order is not None
        assert order.side == OrderSide.SELL
        assert order.quantity == int(5000.0 / 150.0)

    def test_signal_to_order_flat_returns_none(self, order_manager, sample_flat_signal):
        order = order_manager.signal_to_order(
            sample_flat_signal,
            current_price=150.0,
        )
        assert order is None

    def test_signal_to_order_zero_size_returns_none(self, order_manager):
        signal = Signal(
            timestamp=datetime.now(),
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strength=0.8,
            size=0.0,  # Zero size
        )
        order = order_manager.signal_to_order(signal, current_price=150.0)
        assert order is None

    def test_signal_to_order_limit_order(self, order_manager, sample_long_signal):
        order = order_manager.signal_to_order(
            sample_long_signal,
            current_price=150.0,
            order_type=OrderType.LIMIT,
        )

        assert order is not None
        assert order.order_type == OrderType.LIMIT
        assert order.limit_price is not None
        assert order.limit_price > 150.0  # Buy limit is slightly above

    def test_submit_order_market(self, order_manager, sample_order, mock_alpaca_client):
        # Mock the client response
        submitted_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            client_order_id=sample_order.client_order_id,
            broker_order_id="broker_123",
            status=OrderStatus.SUBMITTED,
        )
        mock_alpaca_client.submit_market_order.return_value = submitted_order

        result = order_manager.submit_order(sample_order)

        assert result.broker_order_id == "broker_123"
        assert result.status == OrderStatus.SUBMITTED
        assert sample_order.client_order_id in order_manager.pending_orders
        assert len(order_manager.order_history) == 1

    def test_submit_order_limit(self, order_manager, sample_limit_order, mock_alpaca_client):
        submitted_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            order_type=OrderType.LIMIT,
            limit_price=150.0,
            client_order_id=sample_limit_order.client_order_id,
            broker_order_id="broker_456",
            status=OrderStatus.SUBMITTED,
        )
        mock_alpaca_client.submit_limit_order.return_value = submitted_order

        result = order_manager.submit_order(sample_limit_order)

        assert result.broker_order_id == "broker_456"
        mock_alpaca_client.submit_limit_order.assert_called_once()

    def test_submit_order_failure(self, order_manager, sample_order, mock_alpaca_client):
        mock_alpaca_client.submit_market_order.side_effect = Exception("API error")

        with pytest.raises(Exception):
            order_manager.submit_order(sample_order)

        # Order should be in history with FAILED status
        assert len(order_manager.order_history) == 1
        assert order_manager.order_history[0].status == OrderStatus.FAILED

    def test_submit_market_buy(self, order_manager, mock_alpaca_client):
        submitted_order = Order(
            symbol="MSFT",
            side=OrderSide.BUY,
            quantity=50.0,
            broker_order_id="broker_789",
            status=OrderStatus.SUBMITTED,
        )
        mock_alpaca_client.submit_market_order.return_value = submitted_order

        result = order_manager.submit_market_buy("MSFT", 50.0)

        assert result.symbol == "MSFT"
        assert result.side == OrderSide.BUY
        mock_alpaca_client.submit_market_order.assert_called_once()

    def test_submit_market_sell(self, order_manager, mock_alpaca_client):
        submitted_order = Order(
            symbol="MSFT",
            side=OrderSide.SELL,
            quantity=50.0,
            broker_order_id="broker_sell_789",
            status=OrderStatus.SUBMITTED,
        )
        mock_alpaca_client.submit_market_order.return_value = submitted_order

        result = order_manager.submit_market_sell("MSFT", 50.0)

        assert result.side == OrderSide.SELL

    def test_submit_limit_buy(self, order_manager, mock_alpaca_client):
        submitted_order = Order(
            symbol="GOOGL",
            side=OrderSide.BUY,
            quantity=25.0,
            order_type=OrderType.LIMIT,
            limit_price=140.0,
            broker_order_id="broker_limit_123",
            status=OrderStatus.SUBMITTED,
        )
        mock_alpaca_client.submit_limit_order.return_value = submitted_order

        result = order_manager.submit_limit_buy("GOOGL", 25.0, 140.0)

        assert result.order_type == OrderType.LIMIT
        assert result.limit_price == 140.0

    def test_cancel_order(self, order_manager, sample_order, mock_alpaca_client):
        # First submit the order
        submitted_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            client_order_id=sample_order.client_order_id,
            broker_order_id="broker_to_cancel",
            status=OrderStatus.SUBMITTED,
        )
        mock_alpaca_client.submit_market_order.return_value = submitted_order
        order_manager.submit_order(sample_order)

        # Now cancel it
        mock_alpaca_client.cancel_order.return_value = True
        success = order_manager.cancel_order(sample_order.client_order_id)

        assert success is True
        assert sample_order.client_order_id not in order_manager.pending_orders

    def test_cancel_order_not_found(self, order_manager, mock_alpaca_client):
        success = order_manager.cancel_order("nonexistent_order")
        assert success is False

    def test_cancel_all_orders(self, order_manager, mock_alpaca_client):
        # Submit some orders
        for i in range(3):
            order = Order(
                symbol=f"SYM{i}",
                side=OrderSide.BUY,
                quantity=10.0,
                client_order_id=f"order_{i}",
            )
            submitted = Order(
                symbol=f"SYM{i}",
                side=OrderSide.BUY,
                quantity=10.0,
                client_order_id=f"order_{i}",
                broker_order_id=f"broker_{i}",
                status=OrderStatus.SUBMITTED,
            )
            mock_alpaca_client.submit_market_order.return_value = submitted
            order_manager.submit_order(order)

        mock_alpaca_client.cancel_all_orders.return_value = 3
        count = order_manager.cancel_all_orders()

        assert count == 3
        assert len(order_manager.pending_orders) == 0

    def test_get_order_status(self, order_manager, sample_order, mock_alpaca_client):
        # Submit order
        submitted_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            client_order_id=sample_order.client_order_id,
            broker_order_id="broker_status_123",
            status=OrderStatus.SUBMITTED,
        )
        mock_alpaca_client.submit_market_order.return_value = submitted_order
        order_manager.submit_order(sample_order)

        # Mock get_order to return filled status
        filled_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            client_order_id=sample_order.client_order_id,
            broker_order_id="broker_status_123",
            status=OrderStatus.FILLED,
            filled_quantity=100.0,
            filled_avg_price=150.50,
        )
        mock_alpaca_client.get_order.return_value = filled_order

        result = order_manager.get_order_status(sample_order.client_order_id)

        assert result is not None
        assert result.status == OrderStatus.FILLED
        # Filled orders should be removed from pending
        assert sample_order.client_order_id not in order_manager.pending_orders

    def test_close_position(self, order_manager, mock_alpaca_client):
        close_order = Order(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=100.0,
            broker_order_id="close_123",
            status=OrderStatus.SUBMITTED,
        )
        mock_alpaca_client.close_position.return_value = close_order

        result = order_manager.close_position("AAPL")

        assert result is not None
        mock_alpaca_client.close_position.assert_called_once_with("AAPL")

    def test_close_all_positions(self, order_manager, mock_alpaca_client):
        orders = [
            Order(symbol="AAPL", side=OrderSide.SELL, quantity=100, broker_order_id="close_1", status=OrderStatus.SUBMITTED),
            Order(symbol="MSFT", side=OrderSide.SELL, quantity=50, broker_order_id="close_2", status=OrderStatus.SUBMITTED),
        ]
        mock_alpaca_client.close_all_positions.return_value = orders

        result = order_manager.close_all_positions()

        assert len(result) == 2
        mock_alpaca_client.close_all_positions.assert_called_once()

    def test_get_pending_orders_for_symbol(self, order_manager, mock_alpaca_client):
        # Submit orders for different symbols
        for symbol in ["AAPL", "AAPL", "MSFT"]:
            order = Order(
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=10.0,
                client_order_id=f"order_{symbol}_{datetime.now().timestamp()}",
            )
            submitted = Order(
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=10.0,
                client_order_id=order.client_order_id,
                broker_order_id=f"broker_{order.client_order_id}",
                status=OrderStatus.SUBMITTED,
            )
            mock_alpaca_client.submit_market_order.return_value = submitted
            order_manager.submit_order(order)

        aapl_orders = order_manager.get_pending_orders_for_symbol("AAPL")
        assert len(aapl_orders) == 2

        msft_orders = order_manager.get_pending_orders_for_symbol("MSFT")
        assert len(msft_orders) == 1

        googl_orders = order_manager.get_pending_orders_for_symbol("GOOGL")
        assert len(googl_orders) == 0

    def test_sync_orders(self, order_manager, mock_alpaca_client):
        # Submit an order
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            client_order_id="sync_test_order",
        )
        submitted = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            client_order_id="sync_test_order",
            broker_order_id="broker_sync_123",
            status=OrderStatus.SUBMITTED,
        )
        mock_alpaca_client.submit_market_order.return_value = submitted
        order_manager.submit_order(order)

        # Mock broker orders response with filled status
        filled_broker_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            client_order_id="sync_test_order",
            broker_order_id="broker_sync_123",
            status=OrderStatus.FILLED,
            filled_quantity=100.0,
            filled_avg_price=150.0,
        )
        mock_alpaca_client.get_orders.return_value = [filled_broker_order]

        order_manager.sync_orders()

        # Filled order should be removed from pending
        assert "sync_test_order" not in order_manager.pending_orders
