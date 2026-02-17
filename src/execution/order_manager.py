"""Order manager for submitting and managing orders.

NOTE: Signal conversion functionality requires reimplementation of the strategy module.
See: docs/archive/STATE_VECTOR_HMM_IMPLEMENTATION_PLAN.md
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from src.execution.client import AlpacaClient
from src.execution.orders import Order, OrderSide, OrderType, OrderStatus, OrderTimeInForce
from src.utils.logging import get_logger


# Placeholder types until strategy module is reimplemented
class SignalDirection(Enum):
    """Trading signal direction."""
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass
class SignalMetadata:
    """Metadata for trading signals."""
    regime_label: int | None = None
    regime_sharpe: float | None = None
    momentum_value: float | None = None
    volatility: float | None = None
    pattern_match_count: int | None = None
    pattern_expected_return: float | None = None
    pattern_confidence: float | None = None


@dataclass
class Signal:
    """Placeholder signal class."""
    timestamp: datetime
    symbol: str
    direction: SignalDirection
    strength: float = 1.0
    size: float = 0.0
    metadata: SignalMetadata = field(default_factory=SignalMetadata)

    @property
    def is_long(self) -> bool:
        return self.direction == SignalDirection.LONG

    @property
    def is_short(self) -> bool:
        return self.direction == SignalDirection.SHORT

    @property
    def is_exit(self) -> bool:
        return self.direction == SignalDirection.FLAT


logger = get_logger(__name__)


class OrderManager:
    """Manages order submission and lifecycle.

    Provides a higher-level interface for:
    - Converting signals to orders
    - Submitting orders via the Alpaca client
    - Managing order state and history
    - Handling position reconciliation

    Example:
        client = AlpacaClient(paper=True)
        manager = OrderManager(client)

        # From a signal
        order = manager.signal_to_order(signal, current_price=150.0)
        submitted = manager.submit_order(order)

        # Direct submission
        order = manager.submit_market_buy("AAPL", 100)
    """

    def __init__(
        self,
        client: AlpacaClient,
        default_order_type: OrderType = OrderType.MARKET,
        default_time_in_force: OrderTimeInForce = OrderTimeInForce.DAY,
    ):
        """Initialize the order manager.

        Args:
            client: Alpaca trading client
            default_order_type: Default order type for signal conversion
            default_time_in_force: Default time in force
        """
        logger.debug(
            "Initializing OrderManager: order_type=%s, time_in_force=%s",
            default_order_type, default_time_in_force,
        )
        self._client = client
        self._default_order_type = default_order_type
        self._default_time_in_force = default_time_in_force
        self._pending_orders: dict[str, Order] = {}
        self._order_history: list[Order] = []

    @property
    def pending_orders(self) -> dict[str, Order]:
        """Get pending orders by client order ID."""
        return self._pending_orders.copy()

    @property
    def order_history(self) -> list[Order]:
        """Get order history."""
        return self._order_history.copy()

    def generate_client_order_id(self) -> str:
        """Generate a unique client order ID.

        Returns:
            Unique order ID string
        """
        return f"algo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    def signal_to_order(
        self,
        signal: Signal,
        current_price: float,
        order_type: OrderType | None = None,
        time_in_force: OrderTimeInForce | None = None,
        limit_offset_pct: float = 0.001,
    ) -> Order | None:
        """Convert a trading signal to an order.

        Args:
            signal: Trading signal from strategy
            current_price: Current market price
            order_type: Order type override (None = use default)
            time_in_force: Time in force override (None = use default)
            limit_offset_pct: Offset from current price for limit orders

        Returns:
            Order ready for submission, or None if signal is FLAT
        """
        logger.debug(
            "Converting signal to order: symbol=%s, direction=%s, size=%.2f, price=%.2f",
            signal.symbol, signal.direction.value, signal.size, current_price,
        )
        if signal.direction == SignalDirection.FLAT:
            logger.debug("Signal is FLAT, returning None")
            return None

        # Determine side
        side = OrderSide.BUY if signal.is_long else OrderSide.SELL

        # Calculate quantity from signal size (assumed to be in dollars)
        if signal.size <= 0:
            logger.warning(
                f"Signal has zero or negative size",
                extra={"symbol": signal.symbol, "size": signal.size},
            )
            return None

        quantity = int(signal.size / current_price)
        if quantity <= 0:
            logger.warning(
                f"Calculated quantity is zero",
                extra={
                    "symbol": signal.symbol,
                    "size": signal.size,
                    "price": current_price,
                },
            )
            return None

        # Determine order type and limit price
        effective_order_type = order_type or self._default_order_type
        limit_price = None

        if effective_order_type == OrderType.LIMIT:
            # For buys, place limit slightly above; for sells, slightly below
            offset = current_price * limit_offset_pct
            if side == OrderSide.BUY:
                limit_price = round(current_price + offset, 2)
            else:
                limit_price = round(current_price - offset, 2)

        # Create order
        client_order_id = self.generate_client_order_id()

        order = Order(
            symbol=signal.symbol,
            side=side,
            quantity=float(quantity),
            order_type=effective_order_type,
            time_in_force=time_in_force or self._default_time_in_force,
            limit_price=limit_price,
            client_order_id=client_order_id,
            metadata={
                "signal_timestamp": signal.timestamp.isoformat(),
                "signal_strength": signal.strength,
                "signal_direction": str(signal.direction),
                "momentum_value": signal.metadata.momentum_value,
                "regime_label": signal.metadata.regime_label,
            },
        )

        logger.info(
            f"Created order from signal",
            extra={
                "symbol": signal.symbol,
                "side": str(side),
                "quantity": quantity,
                "order_type": str(effective_order_type),
                "limit_price": limit_price,
                "client_order_id": client_order_id,
            },
        )

        return order

    def submit_order(self, order: Order) -> Order:
        """Submit an order to the broker.

        Args:
            order: Order to submit

        Returns:
            Updated order with broker ID and status
        """
        logger.debug(
            "Submitting order: symbol=%s, side=%s, qty=%.2f, type=%s",
            order.symbol, order.side, order.quantity, order.order_type,
        )
        try:
            if order.order_type == OrderType.MARKET:
                submitted = self._client.submit_market_order(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    time_in_force=order.time_in_force,
                    client_order_id=order.client_order_id,
                )
            elif order.order_type == OrderType.LIMIT:
                submitted = self._client.submit_limit_order(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    limit_price=order.limit_price,
                    time_in_force=order.time_in_force,
                    client_order_id=order.client_order_id,
                )
            else:
                raise ValueError(f"Unsupported order type: {order.order_type}")

            # Update order with broker response
            order.broker_order_id = submitted.broker_order_id
            order.status = submitted.status
            order.submitted_at = datetime.now()
            order.updated_at = datetime.now()

            # Track pending order
            if order.client_order_id:
                self._pending_orders[order.client_order_id] = order

            self._order_history.append(order)
            logger.debug(
                "Order submitted successfully: broker_id=%s, status=%s",
                order.broker_order_id, order.status,
            )

            return order

        except Exception as e:
            order.status = OrderStatus.FAILED
            order.metadata["error"] = str(e)
            order.updated_at = datetime.now()

            logger.error(
                f"Failed to submit order",
                extra={
                    "symbol": order.symbol,
                    "side": str(order.side),
                    "quantity": order.quantity,
                    "error": str(e),
                },
            )

            self._order_history.append(order)
            raise

    def submit_market_buy(
        self,
        symbol: str,
        quantity: float,
        time_in_force: OrderTimeInForce | None = None,
    ) -> Order:
        """Submit a market buy order.

        Args:
            symbol: Asset symbol
            quantity: Number of shares
            time_in_force: Time in force (None = use default)

        Returns:
            Submitted order
        """
        order = Order.market_order(
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=quantity,
            time_in_force=time_in_force or self._default_time_in_force,
            client_order_id=self.generate_client_order_id(),
        )
        return self.submit_order(order)

    def submit_market_sell(
        self,
        symbol: str,
        quantity: float,
        time_in_force: OrderTimeInForce | None = None,
    ) -> Order:
        """Submit a market sell order.

        Args:
            symbol: Asset symbol
            quantity: Number of shares
            time_in_force: Time in force (None = use default)

        Returns:
            Submitted order
        """
        order = Order.market_order(
            symbol=symbol,
            side=OrderSide.SELL,
            quantity=quantity,
            time_in_force=time_in_force or self._default_time_in_force,
            client_order_id=self.generate_client_order_id(),
        )
        return self.submit_order(order)

    def submit_limit_buy(
        self,
        symbol: str,
        quantity: float,
        limit_price: float,
        time_in_force: OrderTimeInForce | None = None,
    ) -> Order:
        """Submit a limit buy order.

        Args:
            symbol: Asset symbol
            quantity: Number of shares
            limit_price: Limit price
            time_in_force: Time in force (None = use default)

        Returns:
            Submitted order
        """
        order = Order.limit_order(
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=quantity,
            limit_price=limit_price,
            time_in_force=time_in_force or self._default_time_in_force,
            client_order_id=self.generate_client_order_id(),
        )
        return self.submit_order(order)

    def cancel_order(self, client_order_id: str) -> bool:
        """Cancel an order by client order ID.

        Args:
            client_order_id: Client order ID

        Returns:
            True if cancelled successfully
        """
        logger.debug("Cancelling order: client_order_id=%s", client_order_id)
        order = self._pending_orders.get(client_order_id)
        if order is None:
            logger.warning(f"Order not found for cancellation", extra={"client_order_id": client_order_id})
            return False

        if not order.broker_order_id:
            logger.warning(f"Order has no broker ID", extra={"client_order_id": client_order_id})
            return False

        success = self._client.cancel_order(order.broker_order_id)
        if success:
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now()
            del self._pending_orders[client_order_id]
            logger.debug("Order cancelled: broker_id=%s", order.broker_order_id)

        return success

    def cancel_all_orders(self) -> int:
        """Cancel all pending orders.

        Returns:
            Number of orders cancelled
        """
        logger.debug("Cancelling all orders: %d pending", len(self._pending_orders))
        count = self._client.cancel_all_orders()

        # Update local tracking
        for order in self._pending_orders.values():
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now()

        self._pending_orders.clear()
        logger.debug("Cancelled %d orders", count)
        return count

    def close_position(self, symbol: str) -> Order | None:
        """Close entire position for a symbol.

        Args:
            symbol: Asset symbol

        Returns:
            Closing order or None if no position
        """
        return self._client.close_position(symbol)

    def close_all_positions(self) -> list[Order]:
        """Close all open positions.

        Returns:
            List of closing orders
        """
        return self._client.close_all_positions()

    def get_order_status(self, client_order_id: str) -> Order | None:
        """Get current order status.

        Args:
            client_order_id: Client order ID

        Returns:
            Updated order or None if not found
        """
        order = self._pending_orders.get(client_order_id)
        if order is None or not order.broker_order_id:
            return None

        updated = self._client.get_order(order.broker_order_id)
        if updated:
            # Update local order
            order.status = updated.status
            order.filled_quantity = updated.filled_quantity
            order.filled_avg_price = updated.filled_avg_price
            order.filled_at = updated.filled_at
            order.updated_at = datetime.now()

            # Remove from pending if terminal
            if order.status.is_terminal and client_order_id in self._pending_orders:
                del self._pending_orders[client_order_id]

        return order

    def sync_orders(self) -> None:
        """Synchronize local order state with broker.

        Fetches current order states from broker and updates local tracking.
        """
        broker_orders = self._client.get_orders(status="all", limit=100)

        # Build lookup by broker order ID
        broker_lookup = {o.broker_order_id: o for o in broker_orders}

        # Update local orders
        to_remove = []
        for client_id, order in self._pending_orders.items():
            if order.broker_order_id in broker_lookup:
                broker_order = broker_lookup[order.broker_order_id]
                order.status = broker_order.status
                order.filled_quantity = broker_order.filled_quantity
                order.filled_avg_price = broker_order.filled_avg_price
                order.filled_at = broker_order.filled_at
                order.updated_at = datetime.now()

                if order.status.is_terminal:
                    to_remove.append(client_id)

        # Remove terminal orders from pending
        for client_id in to_remove:
            del self._pending_orders[client_id]

        logger.info(
            f"Synced orders",
            extra={
                "pending": len(self._pending_orders),
                "terminal_removed": len(to_remove),
            },
        )

    def get_pending_orders_for_symbol(self, symbol: str) -> list[Order]:
        """Get pending orders for a specific symbol.

        Args:
            symbol: Asset symbol

        Returns:
            List of pending orders
        """
        return [o for o in self._pending_orders.values() if o.symbol == symbol]
