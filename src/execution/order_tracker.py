"""Order tracker for monitoring order status and fills."""

import time
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.execution.client import AlpacaClient
from src.execution.orders import Order, OrderStatus
from src.utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class OrderUpdate:
    """Represents an order status update.

    Attributes:
        order: Updated order
        previous_status: Status before update
        new_status: Status after update
        timestamp: When update occurred
        is_fill: Whether this update includes a fill
        fill_quantity: Quantity filled in this update
        fill_price: Fill price in this update
    """

    order: Order
    previous_status: OrderStatus
    new_status: OrderStatus
    timestamp: datetime = field(default_factory=datetime.now)
    is_fill: bool = False
    fill_quantity: float = 0.0
    fill_price: float = 0.0

    @property
    def status_changed(self) -> bool:
        """Check if status changed."""
        return self.previous_status != self.new_status


class OrderTracker:
    """Tracks order status updates and fills.

    Provides:
    - Periodic polling of order status
    - Callback notifications on status changes
    - Fill tracking and notifications
    - Position update tracking

    Example:
        tracker = OrderTracker(client)

        # Register callbacks
        tracker.on_fill(handle_fill)
        tracker.on_status_change(handle_status)

        # Track orders
        tracker.track_order(order)

        # Start tracking (in background)
        tracker.start()

        # Stop tracking
        tracker.stop()
    """

    def __init__(
        self,
        client: AlpacaClient,
        poll_interval: float = 1.0,
        max_tracked_orders: int = 100,
    ):
        """Initialize the order tracker.

        Args:
            client: Alpaca trading client
            poll_interval: Seconds between status polls
            max_tracked_orders: Maximum orders to track simultaneously
        """
        self._client = client
        self._poll_interval = poll_interval
        self._max_tracked_orders = max_tracked_orders

        # Order tracking
        self._tracked_orders: dict[str, Order] = {}
        self._previous_fills: dict[str, float] = {}  # broker_id -> last known filled_qty

        # Callbacks
        self._fill_callbacks: list[Callable[[OrderUpdate], None]] = []
        self._status_callbacks: list[Callable[[OrderUpdate], None]] = []
        self._error_callbacks: list[Callable[[str, Exception], None]] = []

        # Threading
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def tracked_orders(self) -> dict[str, Order]:
        """Get currently tracked orders."""
        with self._lock:
            return self._tracked_orders.copy()

    @property
    def is_running(self) -> bool:
        """Check if tracker is running."""
        return self._running

    def on_fill(self, callback: Callable[[OrderUpdate], None]) -> None:
        """Register a callback for fill events.

        Args:
            callback: Function called with OrderUpdate on fills
        """
        self._fill_callbacks.append(callback)

    def on_status_change(self, callback: Callable[[OrderUpdate], None]) -> None:
        """Register a callback for status change events.

        Args:
            callback: Function called with OrderUpdate on status changes
        """
        self._status_callbacks.append(callback)

    def on_error(self, callback: Callable[[str, Exception], None]) -> None:
        """Register a callback for error events.

        Args:
            callback: Function called with (order_id, exception) on errors
        """
        self._error_callbacks.append(callback)

    def track_order(self, order: Order) -> None:
        """Start tracking an order.

        Args:
            order: Order to track
        """
        if not order.broker_order_id:
            logger.warning(
                f"Cannot track order without broker ID",
                extra={"client_order_id": order.client_order_id},
            )
            return

        with self._lock:
            if len(self._tracked_orders) >= self._max_tracked_orders:
                # Remove oldest terminal orders first
                terminal_ids = [
                    oid for oid, o in self._tracked_orders.items()
                    if o.status.is_terminal
                ]
                for oid in terminal_ids[:10]:  # Remove up to 10
                    del self._tracked_orders[oid]
                    self._previous_fills.pop(oid, None)

                # If still at capacity after removing terminal orders, remove oldest active orders
                if len(self._tracked_orders) >= self._max_tracked_orders:
                    # Sort by created_at and remove oldest
                    sorted_orders = sorted(
                        self._tracked_orders.items(),
                        key=lambda x: x[1].created_at,
                    )
                    for oid, _ in sorted_orders[:5]:  # Remove up to 5 oldest
                        if len(self._tracked_orders) >= self._max_tracked_orders:
                            del self._tracked_orders[oid]
                            self._previous_fills.pop(oid, None)

            self._tracked_orders[order.broker_order_id] = order
            self._previous_fills[order.broker_order_id] = order.filled_quantity

        logger.debug(
            f"Tracking order",
            extra={
                "broker_order_id": order.broker_order_id,
                "symbol": order.symbol,
                "status": str(order.status),
            },
        )

    def untrack_order(self, broker_order_id: str) -> None:
        """Stop tracking an order.

        Args:
            broker_order_id: Broker order ID
        """
        with self._lock:
            self._tracked_orders.pop(broker_order_id, None)
            self._previous_fills.pop(broker_order_id, None)

    def start(self) -> None:
        """Start the tracking thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

        logger.info("Order tracker started")

    def stop(self) -> None:
        """Stop the tracking thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

        logger.info("Order tracker stopped")

    def poll_once(self) -> list[OrderUpdate]:
        """Poll order status once (synchronous).

        Returns:
            List of order updates detected
        """
        updates = []

        with self._lock:
            order_ids = list(self._tracked_orders.keys())

        for broker_order_id in order_ids:
            try:
                update = self._check_order(broker_order_id)
                if update:
                    updates.append(update)
                    self._notify_callbacks(update)
            except Exception as e:
                logger.error(
                    f"Error checking order",
                    extra={"broker_order_id": broker_order_id, "error": str(e)},
                )
                self._notify_error(broker_order_id, e)

        return updates

    def wait_for_fill(
        self,
        broker_order_id: str,
        timeout: float = 60.0,
        poll_interval: float = 0.5,
    ) -> Order | None:
        """Wait for an order to fill.

        Args:
            broker_order_id: Broker order ID
            timeout: Maximum wait time in seconds
            poll_interval: Poll interval in seconds

        Returns:
            Filled order or None if timeout
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            order = self._client.get_order(broker_order_id)
            if order is None:
                return None

            if order.status == OrderStatus.FILLED:
                return order

            if order.status.is_terminal:
                # Terminal but not filled (cancelled, rejected, etc.)
                return order

            time.sleep(poll_interval)

        return None

    def _poll_loop(self) -> None:
        """Background polling loop."""
        while self._running:
            try:
                self.poll_once()
            except Exception as e:
                logger.error(f"Error in poll loop", extra={"error": str(e)})

            time.sleep(self._poll_interval)

    def _check_order(self, broker_order_id: str) -> OrderUpdate | None:
        """Check a single order for updates.

        Args:
            broker_order_id: Broker order ID

        Returns:
            OrderUpdate if changes detected, None otherwise
        """
        with self._lock:
            local_order = self._tracked_orders.get(broker_order_id)
            if local_order is None:
                return None

            previous_status = local_order.status
            previous_filled = self._previous_fills.get(broker_order_id, 0.0)

        # Fetch current state from broker
        broker_order = self._client.get_order(broker_order_id)
        if broker_order is None:
            return None

        # Check for changes
        status_changed = broker_order.status != previous_status
        new_fill = broker_order.filled_quantity > previous_filled

        if not status_changed and not new_fill:
            return None

        # Calculate fill delta
        fill_quantity = broker_order.filled_quantity - previous_filled
        fill_price = broker_order.filled_avg_price if new_fill else 0.0

        # Update local tracking
        with self._lock:
            if broker_order_id in self._tracked_orders:
                order = self._tracked_orders[broker_order_id]
                order.status = broker_order.status
                order.filled_quantity = broker_order.filled_quantity
                order.filled_avg_price = broker_order.filled_avg_price
                order.filled_at = broker_order.filled_at
                order.updated_at = datetime.now()

                self._previous_fills[broker_order_id] = broker_order.filled_quantity

                # Remove from tracking if terminal
                if order.status.is_terminal:
                    del self._tracked_orders[broker_order_id]
                    self._previous_fills.pop(broker_order_id, None)

        update = OrderUpdate(
            order=broker_order,
            previous_status=previous_status,
            new_status=broker_order.status,
            is_fill=new_fill,
            fill_quantity=fill_quantity,
            fill_price=fill_price,
        )

        logger.info(
            f"Order update detected",
            extra={
                "broker_order_id": broker_order_id,
                "symbol": broker_order.symbol,
                "previous_status": str(previous_status),
                "new_status": str(broker_order.status),
                "is_fill": new_fill,
                "fill_quantity": fill_quantity,
            },
        )

        return update

    def _notify_callbacks(self, update: OrderUpdate) -> None:
        """Notify registered callbacks of an update.

        Args:
            update: Order update to notify
        """
        # Notify fill callbacks
        if update.is_fill:
            for callback in self._fill_callbacks:
                try:
                    callback(update)
                except Exception as e:
                    logger.error(f"Fill callback error", extra={"error": str(e)})

        # Notify status change callbacks
        if update.status_changed:
            for callback in self._status_callbacks:
                try:
                    callback(update)
                except Exception as e:
                    logger.error(f"Status callback error", extra={"error": str(e)})

    def _notify_error(self, order_id: str, exception: Exception) -> None:
        """Notify error callbacks.

        Args:
            order_id: Order ID that caused error
            exception: Exception that occurred
        """
        for callback in self._error_callbacks:
            try:
                callback(order_id, exception)
            except Exception as e:
                logger.error(f"Error callback error", extra={"error": str(e)})


class PositionTracker:
    """Tracks position changes based on fill events.

    Maintains local position state synchronized with broker.

    Example:
        tracker = PositionTracker(client)
        tracker.sync()  # Initial sync

        # Get position
        position = tracker.get_position("AAPL")
    """

    def __init__(self, client: AlpacaClient):
        """Initialize position tracker.

        Args:
            client: Alpaca trading client
        """
        self._client = client
        self._positions: dict[str, float] = {}  # symbol -> quantity
        self._avg_costs: dict[str, float] = {}  # symbol -> avg cost
        self._last_sync: datetime | None = None
        self._lock = threading.Lock()

    @property
    def positions(self) -> dict[str, float]:
        """Get current positions."""
        with self._lock:
            return self._positions.copy()

    def get_position(self, symbol: str) -> float:
        """Get position quantity for a symbol.

        Args:
            symbol: Asset symbol

        Returns:
            Position quantity (0 if no position)
        """
        with self._lock:
            return self._positions.get(symbol, 0.0)

    def get_avg_cost(self, symbol: str) -> float:
        """Get average cost for a symbol.

        Args:
            symbol: Asset symbol

        Returns:
            Average cost (0 if no position)
        """
        with self._lock:
            return self._avg_costs.get(symbol, 0.0)

    def sync(self) -> None:
        """Synchronize positions with broker."""
        positions = self._client.get_positions()

        with self._lock:
            self._positions.clear()
            self._avg_costs.clear()

            for pos in positions:
                self._positions[pos.symbol] = pos.quantity
                self._avg_costs[pos.symbol] = pos.avg_entry_price

            self._last_sync = datetime.now()

        logger.info(
            f"Synced positions",
            extra={"count": len(positions)},
        )

    def update_from_fill(self, update: OrderUpdate) -> None:
        """Update position based on a fill.

        Args:
            update: Fill update
        """
        if not update.is_fill:
            return

        order = update.order
        symbol = order.symbol
        fill_qty = update.fill_quantity
        fill_price = update.fill_price

        with self._lock:
            current_qty = self._positions.get(symbol, 0.0)
            current_cost = self._avg_costs.get(symbol, 0.0)

            # Determine direction
            if order.is_buy:
                new_qty = current_qty + fill_qty
                # Update average cost for buys
                if new_qty > 0:
                    total_cost = (current_qty * current_cost) + (fill_qty * fill_price)
                    new_cost = total_cost / new_qty
                else:
                    new_cost = fill_price
            else:
                new_qty = current_qty - fill_qty
                # Keep cost for sells (used for P&L calculation)
                new_cost = current_cost

            if abs(new_qty) < 1e-9:
                # Position closed
                self._positions.pop(symbol, None)
                self._avg_costs.pop(symbol, None)
            else:
                self._positions[symbol] = new_qty
                self._avg_costs[symbol] = new_cost

        logger.debug(
            f"Position updated from fill",
            extra={
                "symbol": symbol,
                "fill_qty": fill_qty,
                "fill_price": fill_price,
                "new_qty": new_qty,
            },
        )
