"""Alpaca trading client for live and paper trading."""

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetOrdersRequest,
    MarketOrderRequest,
    LimitOrderRequest,
    QueryOrderStatus,
)
from alpaca.trading.enums import (
    OrderSide as AlpacaOrderSide,
    OrderType as AlpacaOrderType,
    TimeInForce as AlpacaTimeInForce,
)
from alpaca.common.exceptions import APIError

from src.execution.orders import Order, OrderSide, OrderType, OrderStatus, OrderTimeInForce
from src.utils.logging import get_logger


logger = get_logger(__name__)


@dataclass
class AccountInfo:
    """Account information from broker.

    Attributes:
        account_id: Broker account ID
        buying_power: Available buying power
        cash: Cash balance
        portfolio_value: Total portfolio value
        equity: Account equity
        last_equity: Previous day equity
        long_market_value: Long positions value
        short_market_value: Short positions value
        initial_margin: Initial margin requirement
        maintenance_margin: Maintenance margin
        daytrade_count: Pattern day trade count
        pattern_day_trader: Is pattern day trader
        trading_blocked: Is trading blocked
        transfers_blocked: Are transfers blocked
        account_blocked: Is account blocked
    """

    account_id: str
    buying_power: float
    cash: float
    portfolio_value: float
    equity: float
    last_equity: float
    long_market_value: float
    short_market_value: float
    initial_margin: float
    maintenance_margin: float
    daytrade_count: int
    pattern_day_trader: bool
    trading_blocked: bool
    transfers_blocked: bool
    account_blocked: bool


@dataclass
class PositionInfo:
    """Position information from broker.

    Attributes:
        symbol: Asset symbol
        quantity: Number of shares (negative for short)
        market_value: Current market value
        avg_entry_price: Average entry price
        unrealized_pl: Unrealized P&L
        unrealized_pl_pct: Unrealized P&L percentage
        current_price: Current market price
        side: Long or short
    """

    symbol: str
    quantity: float
    market_value: float
    avg_entry_price: float
    unrealized_pl: float
    unrealized_pl_pct: float
    current_price: float
    side: str


@dataclass
class TradeFillInfo:
    """Trade fill information from broker.

    Attributes:
        id: Activity ID from broker (unique identifier)
        order_id: Order ID this fill belongs to
        symbol: Asset symbol
        side: 'buy' or 'sell'
        quantity: Number of shares filled
        price: Fill price
        transaction_time: When the fill occurred
        order_status: Status of the order (filled, partially_filled)
        leaves_qty: Remaining quantity on the order
        cumulative_qty: Total quantity filled so far
        raw_data: Raw response from broker
    """

    id: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    transaction_time: datetime
    order_status: str
    leaves_qty: float
    cumulative_qty: float
    raw_data: dict = field(default_factory=dict)


class AlpacaClient:
    """Client for connecting to Alpaca trading API.

    Supports both paper and live trading endpoints.
    Provides methods for:
    - Account information queries
    - Position management
    - Order submission and management

    Example:
        client = AlpacaClient(paper=True)
        account = client.get_account()
        positions = client.get_positions()
    """

    # API endpoint URLs
    PAPER_URL = "https://paper-api.alpaca.markets"
    LIVE_URL = "https://api.alpaca.markets"

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        paper: bool = True,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """Initialize the Alpaca trading client.

        Args:
            api_key: Alpaca API key (defaults to ALPACA_API_KEY env var)
            secret_key: Alpaca secret key (defaults to ALPACA_SECRET_KEY env var)
            paper: Use paper trading (default True)
            max_retries: Maximum retry attempts on failure
            retry_delay: Base delay between retries in seconds
        """
        self.api_key = api_key or os.environ.get("ALPACA_API_KEY")
        self.secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")
        self.paper = paper
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Alpaca API credentials required. Set ALPACA_API_KEY and "
                "ALPACA_SECRET_KEY environment variables or pass directly."
            )

        # Initialize trading client
        self._client = TradingClient(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=self.paper,
        )

        logger.info(
            f"Initialized Alpaca client",
            extra={
                "paper": self.paper,
                "endpoint": self.PAPER_URL if self.paper else self.LIVE_URL,
            },
        )

    def _retry_with_backoff(self, operation: str, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute operation with exponential backoff retry.

        Args:
            operation: Description of the operation (for logging)
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Last exception if all retries fail
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except APIError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"API error on {operation}, retrying",
                        extra={
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries,
                            "delay": delay,
                            "error": str(e),
                        },
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"API error on {operation}, max retries exceeded",
                        extra={"error": str(e)},
                    )
            except Exception as e:
                last_error = e
                logger.error(
                    f"Unexpected error on {operation}",
                    extra={"error": str(e)},
                )
                break

        raise last_error if last_error else RuntimeError(f"Failed: {operation}")

    def get_account(self) -> AccountInfo:
        """Get current account information.

        Returns:
            AccountInfo with current account state
        """
        account = self._retry_with_backoff(
            "get_account",
            self._client.get_account,
        )

        return AccountInfo(
            account_id=str(account.id),
            buying_power=float(account.buying_power),
            cash=float(account.cash),
            portfolio_value=float(account.portfolio_value),
            equity=float(account.equity),
            last_equity=float(account.last_equity),
            long_market_value=float(account.long_market_value),
            short_market_value=float(account.short_market_value),
            initial_margin=float(account.initial_margin),
            maintenance_margin=float(account.maintenance_margin),
            daytrade_count=int(account.daytrade_count),
            pattern_day_trader=bool(account.pattern_day_trader),
            trading_blocked=bool(account.trading_blocked),
            transfers_blocked=bool(account.transfers_blocked),
            account_blocked=bool(account.account_blocked),
        )

    def get_positions(self) -> list[PositionInfo]:
        """Get all current positions.

        Returns:
            List of PositionInfo for all open positions
        """
        positions = self._retry_with_backoff(
            "get_positions",
            self._client.get_all_positions,
        )

        result = []
        for pos in positions:
            result.append(
                PositionInfo(
                    symbol=pos.symbol,
                    quantity=float(pos.qty),
                    market_value=float(pos.market_value),
                    avg_entry_price=float(pos.avg_entry_price),
                    unrealized_pl=float(pos.unrealized_pl),
                    unrealized_pl_pct=float(pos.unrealized_plpc) * 100,
                    current_price=float(pos.current_price),
                    side=pos.side.value,
                )
            )

        return result

    def get_position(self, symbol: str) -> PositionInfo | None:
        """Get position for a specific symbol.

        Args:
            symbol: Asset symbol

        Returns:
            PositionInfo or None if no position exists
        """
        try:
            pos = self._retry_with_backoff(
                f"get_position_{symbol}",
                self._client.get_open_position,
                symbol,
            )

            return PositionInfo(
                symbol=pos.symbol,
                quantity=float(pos.qty),
                market_value=float(pos.market_value),
                avg_entry_price=float(pos.avg_entry_price),
                unrealized_pl=float(pos.unrealized_pl),
                unrealized_pl_pct=float(pos.unrealized_plpc) * 100,
                current_price=float(pos.current_price),
                side=pos.side.value,
            )
        except APIError as e:
            if "position does not exist" in str(e).lower():
                return None
            raise

    def close_position(self, symbol: str, quantity: float | None = None, strategy_id: int | None = None) -> Order | None:
        """Close a position for a symbol.

        Args:
            symbol: Asset symbol
            quantity: Quantity to close (None = close all)
            strategy_id: Optional strategy ID for tracking

        Returns:
            Order for the closing trade, or None if no position
        """
        position = self.get_position(symbol)
        if position is None:
            return None

        try:
            if quantity is None:
                # Close entire position
                response = self._retry_with_backoff(
                    f"close_position_{symbol}",
                    self._client.close_position,
                    symbol,
                )
            else:
                # Partial close - submit opposite order
                side = OrderSide.SELL if position.quantity > 0 else OrderSide.BUY
                return self.submit_market_order(symbol, side, abs(quantity), strategy_id=strategy_id)

            return self._convert_alpaca_order(response)

        except APIError as e:
            logger.error(
                f"Failed to close position",
                extra={"symbol": symbol, "error": str(e)},
            )
            raise

    def close_all_positions(self) -> list[Order]:
        """Close all open positions.

        Returns:
            List of closing orders
        """
        try:
            responses = self._retry_with_backoff(
                "close_all_positions",
                self._client.close_all_positions,
                cancel_orders=True,
            )

            orders = []
            for response in responses:
                if hasattr(response, "body"):
                    orders.append(self._convert_alpaca_order(response.body))

            logger.info(f"Closed all positions", extra={"count": len(orders)})
            return orders

        except APIError as e:
            logger.error(f"Failed to close all positions", extra={"error": str(e)})
            raise

    def submit_market_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        time_in_force: OrderTimeInForce = OrderTimeInForce.DAY,
        client_order_id: str | None = None,
        strategy_id: int | None = None,
    ) -> Order:
        """Submit a market order.

        Args:
            symbol: Asset symbol
            side: Buy or sell
            quantity: Number of shares
            time_in_force: Time in force
            client_order_id: Optional client order ID
            strategy_id: Optional strategy ID for tracking

        Returns:
            Order with broker order ID
        """
        alpaca_side = AlpacaOrderSide.BUY if side == OrderSide.BUY else AlpacaOrderSide.SELL
        alpaca_tif = self._convert_time_in_force(time_in_force)

        # If strategy_id is provided and client_order_id is not, embed strategy_id in client_order_id
        order_client_id = client_order_id
        if strategy_id is not None and not order_client_id:
            import uuid
            order_client_id = f"strat_{strategy_id}_{uuid.uuid4().hex[:8]}"

        request = MarketOrderRequest(
            symbol=symbol,
            qty=quantity,
            side=alpaca_side,
            time_in_force=alpaca_tif,
            client_order_id=order_client_id,
        )

        response = self._retry_with_backoff(
            f"submit_market_order_{symbol}",
            self._client.submit_order,
            request,
        )

        order = self._convert_alpaca_order(response)

        log_extra = {
            "symbol": symbol,
            "side": str(side),
            "quantity": quantity,
            "broker_order_id": order.broker_order_id,
        }
        if strategy_id is not None:
            log_extra["strategy_id"] = strategy_id

        logger.info(
            f"Submitted market order",
            extra=log_extra,
        )

        return order

    def submit_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        limit_price: float,
        time_in_force: OrderTimeInForce = OrderTimeInForce.DAY,
        client_order_id: str | None = None,
        strategy_id: int | None = None,
    ) -> Order:
        """Submit a limit order.

        Args:
            symbol: Asset symbol
            side: Buy or sell
            quantity: Number of shares
            limit_price: Limit price
            time_in_force: Time in force
            client_order_id: Optional client order ID
            strategy_id: Optional strategy ID for tracking

        Returns:
            Order with broker order ID
        """
        alpaca_side = AlpacaOrderSide.BUY if side == OrderSide.BUY else AlpacaOrderSide.SELL
        alpaca_tif = self._convert_time_in_force(time_in_force)

        # If strategy_id is provided and client_order_id is not, embed strategy_id in client_order_id
        order_client_id = client_order_id
        if strategy_id is not None and not order_client_id:
            import uuid
            order_client_id = f"strat_{strategy_id}_{uuid.uuid4().hex[:8]}"

        request = LimitOrderRequest(
            symbol=symbol,
            qty=quantity,
            side=alpaca_side,
            time_in_force=alpaca_tif,
            limit_price=limit_price,
            client_order_id=order_client_id,
        )

        response = self._retry_with_backoff(
            f"submit_limit_order_{symbol}",
            self._client.submit_order,
            request,
        )

        order = self._convert_alpaca_order(response)

        log_extra = {
            "symbol": symbol,
            "side": str(side),
            "quantity": quantity,
            "limit_price": limit_price,
            "broker_order_id": order.broker_order_id,
        }
        if strategy_id is not None:
            log_extra["strategy_id"] = strategy_id

        logger.info(
            f"Submitted limit order",
            extra=log_extra,
        )

        return order

    def get_order(self, order_id: str) -> Order | None:
        """Get order by broker order ID.

        Args:
            order_id: Broker order ID

        Returns:
            Order or None if not found
        """
        try:
            response = self._retry_with_backoff(
                f"get_order_{order_id}",
                self._client.get_order_by_id,
                order_id,
            )
            return self._convert_alpaca_order(response)
        except APIError as e:
            if "order not found" in str(e).lower():
                return None
            raise

    def get_orders(
        self,
        status: str = "open",
        limit: int = 500,
        symbols: list[str] | None = None,
    ) -> list[Order]:
        """Get orders with filters.

        Args:
            status: Order status filter ('open', 'closed', 'all')
            limit: Maximum number of orders to return
            symbols: Filter by symbols

        Returns:
            List of orders
        """
        status_map = {
            "open": QueryOrderStatus.OPEN,
            "closed": QueryOrderStatus.CLOSED,
            "all": QueryOrderStatus.ALL,
        }

        request = GetOrdersRequest(
            status=status_map.get(status, QueryOrderStatus.ALL),
            limit=limit,
            symbols=symbols,
        )

        response = self._retry_with_backoff(
            "get_orders",
            self._client.get_orders,
            request,
        )

        return [self._convert_alpaca_order(o) for o in response]

    def get_trade_fills(
        self,
        status: str = "closed",
        limit: int = 500,
        symbols: list[str] | None = None,
    ) -> list[TradeFillInfo]:
        """Get trade fills from Alpaca by fetching filled orders.

        Fetches closed orders and extracts fill information.

        Args:
            status: Order status filter ('closed' for fills)
            limit: Maximum number of orders to return
            symbols: Filter by symbols

        Returns:
            List of TradeFillInfo for all fills
        """
        try:
            # Get closed (filled) orders
            orders = self.get_orders(status=status, limit=limit, symbols=symbols)

            fills = []
            for order in orders:
                # Only include filled or partially filled orders
                if order.filled_quantity <= 0:
                    continue

                try:
                    fill = TradeFillInfo(
                        id=order.broker_order_id or "",
                        order_id=order.broker_order_id or "",
                        symbol=order.symbol,
                        side=str(order.side.value) if hasattr(order.side, 'value') else str(order.side),
                        quantity=order.filled_quantity,
                        price=order.filled_avg_price,
                        transaction_time=order.filled_at or order.submitted_at or datetime.now(),
                        order_status=str(order.status.value) if hasattr(order.status, 'value') else str(order.status),
                        leaves_qty=order.remaining_quantity,
                        cumulative_qty=order.filled_quantity,
                        raw_data={
                            "broker_order_id": order.broker_order_id,
                            "client_order_id": order.client_order_id,
                            "symbol": order.symbol,
                            "side": str(order.side),
                            "order_type": str(order.order_type),
                            "qty": str(order.quantity),
                            "filled_qty": str(order.filled_quantity),
                            "filled_avg_price": str(order.filled_avg_price),
                            "status": str(order.status),
                            "submitted_at": str(order.submitted_at) if order.submitted_at else None,
                            "filled_at": str(order.filled_at) if order.filled_at else None,
                        }
                    )
                    fills.append(fill)
                except Exception as e:
                    logger.warning(f"Failed to parse order as fill: {e}, order={order}")
                    continue

            logger.info(f"Fetched {len(fills)} trade fills from Alpaca (from {len(orders)} closed orders)")
            return fills

        except Exception as e:
            logger.error(f"Failed to get trade fills: {e}")
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order by broker order ID.

        Args:
            order_id: Broker order ID

        Returns:
            True if cancelled successfully
        """
        try:
            self._retry_with_backoff(
                f"cancel_order_{order_id}",
                self._client.cancel_order_by_id,
                order_id,
            )

            logger.info(f"Cancelled order", extra={"order_id": order_id})
            return True

        except APIError as e:
            logger.error(f"Failed to cancel order", extra={"order_id": order_id, "error": str(e)})
            return False

    def cancel_all_orders(self) -> int:
        """Cancel all open orders.

        Returns:
            Number of orders cancelled
        """
        try:
            responses = self._retry_with_backoff(
                "cancel_all_orders",
                self._client.cancel_orders,
            )

            count = len(responses) if responses else 0
            logger.info(f"Cancelled all orders", extra={"count": count})
            return count

        except APIError as e:
            logger.error(f"Failed to cancel all orders", extra={"error": str(e)})
            raise

    def is_market_open(self) -> bool:
        """Check if the market is currently open.

        Returns:
            True if market is open for trading
        """
        clock = self._retry_with_backoff(
            "get_clock",
            self._client.get_clock,
        )
        return clock.is_open

    def _convert_time_in_force(self, tif: OrderTimeInForce) -> AlpacaTimeInForce:
        """Convert our time in force to Alpaca's."""
        mapping = {
            OrderTimeInForce.DAY: AlpacaTimeInForce.DAY,
            OrderTimeInForce.GTC: AlpacaTimeInForce.GTC,
            OrderTimeInForce.IOC: AlpacaTimeInForce.IOC,
            OrderTimeInForce.FOK: AlpacaTimeInForce.FOK,
            OrderTimeInForce.OPG: AlpacaTimeInForce.OPG,
            OrderTimeInForce.CLS: AlpacaTimeInForce.CLS,
        }
        return mapping.get(tif, AlpacaTimeInForce.DAY)

    def _convert_alpaca_order(self, alpaca_order: Any) -> Order:
        """Convert Alpaca order response to our Order type."""
        # Map Alpaca status to our status
        status_map = {
            "new": OrderStatus.SUBMITTED,
            "accepted": OrderStatus.ACCEPTED,
            "pending_new": OrderStatus.PENDING,
            "accepted_for_bidding": OrderStatus.ACCEPTED,
            "stopped": OrderStatus.CANCELLED,
            "rejected": OrderStatus.REJECTED,
            "suspended": OrderStatus.CANCELLED,
            "calculated": OrderStatus.ACCEPTED,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "filled": OrderStatus.FILLED,
            "done_for_day": OrderStatus.CANCELLED,
            "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED,
            "replaced": OrderStatus.CANCELLED,
            "pending_cancel": OrderStatus.ACCEPTED,
            "pending_replace": OrderStatus.ACCEPTED,
        }

        # Map order type
        type_map = {
            "market": OrderType.MARKET,
            "limit": OrderType.LIMIT,
            "stop": OrderType.STOP,
            "stop_limit": OrderType.STOP_LIMIT,
        }

        # Map side
        side = OrderSide.BUY if alpaca_order.side.value == "buy" else OrderSide.SELL

        # Map time in force
        tif_map = {
            "day": OrderTimeInForce.DAY,
            "gtc": OrderTimeInForce.GTC,
            "ioc": OrderTimeInForce.IOC,
            "fok": OrderTimeInForce.FOK,
            "opg": OrderTimeInForce.OPG,
            "cls": OrderTimeInForce.CLS,
        }

        return Order(
            symbol=alpaca_order.symbol,
            side=side,
            quantity=float(alpaca_order.qty),
            order_type=type_map.get(alpaca_order.order_type.value, OrderType.MARKET),
            time_in_force=tif_map.get(alpaca_order.time_in_force.value, OrderTimeInForce.DAY),
            limit_price=float(alpaca_order.limit_price) if alpaca_order.limit_price else None,
            stop_price=float(alpaca_order.stop_price) if alpaca_order.stop_price else None,
            client_order_id=alpaca_order.client_order_id,
            broker_order_id=str(alpaca_order.id),
            status=status_map.get(alpaca_order.status.value, OrderStatus.PENDING),
            filled_quantity=float(alpaca_order.filled_qty) if alpaca_order.filled_qty else 0.0,
            filled_avg_price=float(alpaca_order.filled_avg_price) if alpaca_order.filled_avg_price else 0.0,
            submitted_at=alpaca_order.submitted_at,
            filled_at=alpaca_order.filled_at,
        )
