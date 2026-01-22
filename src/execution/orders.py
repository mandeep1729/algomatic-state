"""Order data types for the execution module."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class OrderSide(Enum):
    """Order side (buy or sell)."""

    BUY = "buy"
    SELL = "sell"

    def __str__(self) -> str:
        return self.value


class OrderType(Enum):
    """Order type (market or limit)."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

    def __str__(self) -> str:
        return self.value


class OrderStatus(Enum):
    """Order status."""

    PENDING = "pending"  # Created but not submitted
    SUBMITTED = "submitted"  # Submitted to broker
    ACCEPTED = "accepted"  # Accepted by broker
    PARTIALLY_FILLED = "partially_filled"  # Partially filled
    FILLED = "filled"  # Completely filled
    CANCELLED = "cancelled"  # Cancelled by user or system
    REJECTED = "rejected"  # Rejected by broker
    EXPIRED = "expired"  # Expired (time in force)
    FAILED = "failed"  # Failed to submit

    def __str__(self) -> str:
        return self.value

    @property
    def is_terminal(self) -> bool:
        """Check if this is a terminal state."""
        return self in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
            OrderStatus.FAILED,
        )

    @property
    def is_active(self) -> bool:
        """Check if this is an active state."""
        return self in (
            OrderStatus.PENDING,
            OrderStatus.SUBMITTED,
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED,
        )


class OrderTimeInForce(Enum):
    """Time in force for orders."""

    DAY = "day"  # Good for the day
    GTC = "gtc"  # Good 'til cancelled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill
    OPG = "opg"  # Market on open
    CLS = "cls"  # Market on close

    def __str__(self) -> str:
        return self.value


@dataclass
class Order:
    """Represents a trading order.

    Attributes:
        symbol: Asset symbol (e.g., 'AAPL')
        side: Buy or sell
        quantity: Number of shares
        order_type: Market, limit, etc.
        time_in_force: Day, GTC, etc.
        limit_price: Limit price (required for limit orders)
        stop_price: Stop price (required for stop orders)
        client_order_id: Client-assigned order ID
        broker_order_id: Broker-assigned order ID
        status: Current order status
        filled_quantity: Number of shares filled
        filled_avg_price: Average fill price
        submitted_at: When order was submitted
        filled_at: When order was completely filled
        created_at: When order was created locally
        updated_at: When order was last updated
        metadata: Additional order metadata
    """

    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    time_in_force: OrderTimeInForce = OrderTimeInForce.DAY
    limit_price: float | None = None
    stop_price: float | None = None
    client_order_id: str | None = None
    broker_order_id: str | None = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    filled_avg_price: float = 0.0
    submitted_at: datetime | None = None
    filled_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate order parameters."""
        if self.quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {self.quantity}")

        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("Limit price required for limit orders")

        if self.order_type in (OrderType.STOP, OrderType.STOP_LIMIT) and self.stop_price is None:
            raise ValueError("Stop price required for stop orders")

        if self.order_type == OrderType.STOP_LIMIT and self.limit_price is None:
            raise ValueError("Limit price required for stop-limit orders")

    @property
    def is_buy(self) -> bool:
        """Check if this is a buy order."""
        return self.side == OrderSide.BUY

    @property
    def is_sell(self) -> bool:
        """Check if this is a sell order."""
        return self.side == OrderSide.SELL

    @property
    def remaining_quantity(self) -> float:
        """Get remaining unfilled quantity."""
        return self.quantity - self.filled_quantity

    @property
    def is_filled(self) -> bool:
        """Check if order is completely filled."""
        return self.status == OrderStatus.FILLED

    @property
    def is_active(self) -> bool:
        """Check if order is still active."""
        return self.status.is_active

    @property
    def notional_value(self) -> float:
        """Get notional value of the order."""
        price = self.limit_price or self.filled_avg_price or 0.0
        return self.quantity * price

    def update_fill(
        self,
        filled_quantity: float,
        avg_price: float,
        status: OrderStatus | None = None,
    ) -> None:
        """Update order with fill information.

        Args:
            filled_quantity: Total filled quantity
            avg_price: Average fill price
            status: New status (auto-determined if None)
        """
        self.filled_quantity = filled_quantity
        self.filled_avg_price = avg_price
        self.updated_at = datetime.now()

        if status is not None:
            self.status = status
        elif filled_quantity >= self.quantity:
            self.status = OrderStatus.FILLED
            self.filled_at = datetime.now()
        elif filled_quantity > 0:
            self.status = OrderStatus.PARTIALLY_FILLED

    def to_dict(self) -> dict[str, Any]:
        """Convert order to dictionary.

        Returns:
            Dictionary representation of the order
        """
        return {
            "symbol": self.symbol,
            "side": str(self.side),
            "quantity": self.quantity,
            "order_type": str(self.order_type),
            "time_in_force": str(self.time_in_force),
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "client_order_id": self.client_order_id,
            "broker_order_id": self.broker_order_id,
            "status": str(self.status),
            "filled_quantity": self.filled_quantity,
            "filled_avg_price": self.filled_avg_price,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Order":
        """Create order from dictionary.

        Args:
            data: Dictionary with order data

        Returns:
            Order instance
        """

        def parse_datetime(value: str | datetime | None) -> datetime | None:
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(value)

        return cls(
            symbol=data["symbol"],
            side=OrderSide(data["side"]),
            quantity=data["quantity"],
            order_type=OrderType(data.get("order_type", "market")),
            time_in_force=OrderTimeInForce(data.get("time_in_force", "day")),
            limit_price=data.get("limit_price"),
            stop_price=data.get("stop_price"),
            client_order_id=data.get("client_order_id"),
            broker_order_id=data.get("broker_order_id"),
            status=OrderStatus(data.get("status", "pending")),
            filled_quantity=data.get("filled_quantity", 0.0),
            filled_avg_price=data.get("filled_avg_price", 0.0),
            submitted_at=parse_datetime(data.get("submitted_at")),
            filled_at=parse_datetime(data.get("filled_at")),
            created_at=parse_datetime(data.get("created_at")) or datetime.now(),
            updated_at=parse_datetime(data.get("updated_at")) or datetime.now(),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def market_order(
        cls,
        symbol: str,
        side: OrderSide,
        quantity: float,
        time_in_force: OrderTimeInForce = OrderTimeInForce.DAY,
        client_order_id: str | None = None,
        **kwargs: Any,
    ) -> "Order":
        """Create a market order.

        Args:
            symbol: Asset symbol
            side: Buy or sell
            quantity: Number of shares
            time_in_force: Time in force
            client_order_id: Optional client order ID
            **kwargs: Additional order parameters

        Returns:
            Market order instance
        """
        return cls(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=OrderType.MARKET,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            **kwargs,
        )

    @classmethod
    def limit_order(
        cls,
        symbol: str,
        side: OrderSide,
        quantity: float,
        limit_price: float,
        time_in_force: OrderTimeInForce = OrderTimeInForce.DAY,
        client_order_id: str | None = None,
        **kwargs: Any,
    ) -> "Order":
        """Create a limit order.

        Args:
            symbol: Asset symbol
            side: Buy or sell
            quantity: Number of shares
            limit_price: Limit price
            time_in_force: Time in force
            client_order_id: Optional client order ID
            **kwargs: Additional order parameters

        Returns:
            Limit order instance
        """
        return cls(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=limit_price,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            **kwargs,
        )
