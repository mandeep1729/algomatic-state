"""Tests for order tracker."""

from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest
import time

from src.execution.orders import Order, OrderSide, OrderStatus
from src.execution.order_tracker import OrderTracker, OrderUpdate, PositionTracker


class TestOrderUpdate:
    """Tests for OrderUpdate."""

    def test_create_order_update(self, filled_order):
        update = OrderUpdate(
            order=filled_order,
            previous_status=OrderStatus.SUBMITTED,
            new_status=OrderStatus.FILLED,
            is_fill=True,
            fill_quantity=100.0,
            fill_price=150.50,
        )

        assert update.status_changed is True
        assert update.is_fill is True
        assert update.fill_quantity == 100.0

    def test_no_status_change(self, filled_order):
        update = OrderUpdate(
            order=filled_order,
            previous_status=OrderStatus.FILLED,
            new_status=OrderStatus.FILLED,
        )
        assert update.status_changed is False


class TestOrderTracker:
    """Tests for OrderTracker."""

    @pytest.fixture
    def order_tracker(self, mock_alpaca_client):
        """Create an order tracker with mock client."""
        return OrderTracker(mock_alpaca_client, poll_interval=0.1)

    def test_initialization(self, order_tracker):
        assert len(order_tracker.tracked_orders) == 0
        assert order_tracker.is_running is False

    def test_track_order(self, order_tracker, filled_order):
        order_tracker.track_order(filled_order)
        assert filled_order.broker_order_id in order_tracker.tracked_orders

    def test_track_order_without_broker_id(self, order_tracker, sample_order):
        # Order without broker_order_id should not be tracked
        order_tracker.track_order(sample_order)
        assert len(order_tracker.tracked_orders) == 0

    def test_untrack_order(self, order_tracker, filled_order):
        order_tracker.track_order(filled_order)
        order_tracker.untrack_order(filled_order.broker_order_id)
        assert filled_order.broker_order_id not in order_tracker.tracked_orders

    def test_register_fill_callback(self, order_tracker):
        callback = MagicMock()
        order_tracker.on_fill(callback)
        assert callback in order_tracker._fill_callbacks

    def test_register_status_callback(self, order_tracker):
        callback = MagicMock()
        order_tracker.on_status_change(callback)
        assert callback in order_tracker._status_callbacks

    def test_poll_once_detects_fill(self, order_tracker, mock_alpaca_client):
        # Create and track an order
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            broker_order_id="track_test_123",
            status=OrderStatus.SUBMITTED,
        )
        order_tracker.track_order(order)

        # Mock client to return filled order
        filled_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            broker_order_id="track_test_123",
            status=OrderStatus.FILLED,
            filled_quantity=100.0,
            filled_avg_price=150.0,
        )
        mock_alpaca_client.get_order.return_value = filled_order

        # Register callback
        fill_callback = MagicMock()
        order_tracker.on_fill(fill_callback)

        # Poll
        updates = order_tracker.poll_once()

        assert len(updates) == 1
        assert updates[0].is_fill is True
        fill_callback.assert_called_once()

    def test_poll_once_detects_status_change(self, order_tracker, mock_alpaca_client):
        # Create and track an order
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            broker_order_id="status_test_123",
            status=OrderStatus.SUBMITTED,
        )
        order_tracker.track_order(order)

        # Mock client to return accepted order
        accepted_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            broker_order_id="status_test_123",
            status=OrderStatus.ACCEPTED,
            filled_quantity=0.0,
        )
        mock_alpaca_client.get_order.return_value = accepted_order

        # Register callback
        status_callback = MagicMock()
        order_tracker.on_status_change(status_callback)

        # Poll
        updates = order_tracker.poll_once()

        assert len(updates) == 1
        assert updates[0].status_changed is True
        status_callback.assert_called_once()

    def test_terminal_orders_removed_from_tracking(self, order_tracker, mock_alpaca_client):
        # Create and track an order
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            broker_order_id="terminal_test_123",
            status=OrderStatus.SUBMITTED,
        )
        order_tracker.track_order(order)

        # Mock client to return filled order
        filled_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            broker_order_id="terminal_test_123",
            status=OrderStatus.FILLED,
            filled_quantity=100.0,
            filled_avg_price=150.0,
        )
        mock_alpaca_client.get_order.return_value = filled_order

        # Poll
        order_tracker.poll_once()

        # Terminal orders should be removed
        assert "terminal_test_123" not in order_tracker.tracked_orders

    def test_start_and_stop(self, order_tracker):
        order_tracker.start()
        assert order_tracker.is_running is True

        order_tracker.stop()
        assert order_tracker.is_running is False

    def test_wait_for_fill_success(self, order_tracker, mock_alpaca_client):
        # Mock client to return filled order immediately
        filled_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            broker_order_id="wait_test_123",
            status=OrderStatus.FILLED,
            filled_quantity=100.0,
            filled_avg_price=150.0,
        )
        mock_alpaca_client.get_order.return_value = filled_order

        result = order_tracker.wait_for_fill("wait_test_123", timeout=5.0)

        assert result is not None
        assert result.status == OrderStatus.FILLED

    def test_wait_for_fill_timeout(self, order_tracker, mock_alpaca_client):
        # Mock client to always return pending order
        pending_order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            broker_order_id="timeout_test_123",
            status=OrderStatus.SUBMITTED,
        )
        mock_alpaca_client.get_order.return_value = pending_order

        result = order_tracker.wait_for_fill(
            "timeout_test_123",
            timeout=0.5,
            poll_interval=0.1,
        )

        assert result is None

    def test_max_tracked_orders_limit(self, order_tracker):
        order_tracker._max_tracked_orders = 5

        # Add more orders than limit
        for i in range(10):
            order = Order(
                symbol=f"SYM{i}",
                side=OrderSide.BUY,
                quantity=10.0,
                broker_order_id=f"max_test_{i}",
                status=OrderStatus.SUBMITTED,
            )
            order_tracker.track_order(order)

        # Should have at most max_tracked_orders
        assert len(order_tracker.tracked_orders) <= order_tracker._max_tracked_orders


class TestPositionTracker:
    """Tests for PositionTracker."""

    @pytest.fixture
    def position_tracker(self, mock_alpaca_client):
        """Create a position tracker with mock client."""
        return PositionTracker(mock_alpaca_client)

    def test_initialization(self, position_tracker):
        assert len(position_tracker.positions) == 0

    def test_sync_positions(self, position_tracker, mock_alpaca_client, sample_positions):
        mock_alpaca_client.get_positions.return_value = sample_positions

        position_tracker.sync()

        assert position_tracker.get_position("AAPL") == 100.0
        assert position_tracker.get_position("MSFT") == 50.0
        assert position_tracker.get_position("GOOGL") == 0.0

    def test_get_avg_cost(self, position_tracker, mock_alpaca_client, sample_positions):
        mock_alpaca_client.get_positions.return_value = sample_positions

        position_tracker.sync()

        assert position_tracker.get_avg_cost("AAPL") == 145.0
        assert position_tracker.get_avg_cost("MSFT") == 350.0
        assert position_tracker.get_avg_cost("UNKNOWN") == 0.0

    def test_update_from_fill_buy(self, position_tracker, mock_alpaca_client):
        # Sync empty positions first
        mock_alpaca_client.get_positions.return_value = []
        position_tracker.sync()

        # Simulate a buy fill
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            broker_order_id="fill_test_123",
            status=OrderStatus.FILLED,
            filled_quantity=100.0,
            filled_avg_price=150.0,
        )
        update = OrderUpdate(
            order=order,
            previous_status=OrderStatus.SUBMITTED,
            new_status=OrderStatus.FILLED,
            is_fill=True,
            fill_quantity=100.0,
            fill_price=150.0,
        )

        position_tracker.update_from_fill(update)

        assert position_tracker.get_position("AAPL") == 100.0
        assert position_tracker.get_avg_cost("AAPL") == 150.0

    def test_update_from_fill_sell(self, position_tracker, mock_alpaca_client, sample_positions):
        # Sync with existing position
        mock_alpaca_client.get_positions.return_value = sample_positions
        position_tracker.sync()

        # Simulate a sell fill
        order = Order(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=50.0,
            broker_order_id="sell_test_123",
            status=OrderStatus.FILLED,
            filled_quantity=50.0,
            filled_avg_price=155.0,
        )
        update = OrderUpdate(
            order=order,
            previous_status=OrderStatus.SUBMITTED,
            new_status=OrderStatus.FILLED,
            is_fill=True,
            fill_quantity=50.0,
            fill_price=155.0,
        )

        position_tracker.update_from_fill(update)

        assert position_tracker.get_position("AAPL") == 50.0  # 100 - 50

    def test_update_from_fill_closes_position(self, position_tracker, mock_alpaca_client, sample_positions):
        # Sync with existing position
        mock_alpaca_client.get_positions.return_value = sample_positions
        position_tracker.sync()

        # Sell all shares
        order = Order(
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=100.0,
            broker_order_id="close_test_123",
            status=OrderStatus.FILLED,
            filled_quantity=100.0,
            filled_avg_price=155.0,
        )
        update = OrderUpdate(
            order=order,
            previous_status=OrderStatus.SUBMITTED,
            new_status=OrderStatus.FILLED,
            is_fill=True,
            fill_quantity=100.0,
            fill_price=155.0,
        )

        position_tracker.update_from_fill(update)

        assert position_tracker.get_position("AAPL") == 0.0
        assert "AAPL" not in position_tracker.positions

    def test_update_from_non_fill_ignored(self, position_tracker, mock_alpaca_client):
        mock_alpaca_client.get_positions.return_value = []
        position_tracker.sync()

        # Non-fill update
        order = Order(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            broker_order_id="no_fill_test",
            status=OrderStatus.ACCEPTED,
        )
        update = OrderUpdate(
            order=order,
            previous_status=OrderStatus.SUBMITTED,
            new_status=OrderStatus.ACCEPTED,
            is_fill=False,
        )

        position_tracker.update_from_fill(update)

        # Position should not change
        assert position_tracker.get_position("AAPL") == 0.0
