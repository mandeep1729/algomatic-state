"""Risk manager for pre-trade risk controls and position limits."""

from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any

from src.execution.client import AlpacaClient, AccountInfo, PositionInfo
from src.execution.orders import Order, OrderSide
from src.utils.logging import get_logger


logger = get_logger(__name__)


class RiskViolationType(Enum):
    """Types of risk violations."""

    POSITION_SIZE = "position_size"
    PORTFOLIO_CONCENTRATION = "portfolio_concentration"
    DAILY_LOSS = "daily_loss"
    MAX_DRAWDOWN = "max_drawdown"
    BUYING_POWER = "buying_power"
    SYMBOL_LIMIT = "symbol_limit"
    ORDER_SIZE = "order_size"
    TRADING_BLOCKED = "trading_blocked"


@dataclass
class RiskViolation:
    """Represents a risk limit violation.

    Attributes:
        violation_type: Type of violation
        message: Human-readable description
        current_value: Current value that violated limit
        limit_value: The limit that was violated
        order: Order that would cause violation (if applicable)
        timestamp: When violation occurred
    """

    violation_type: RiskViolationType
    message: str
    current_value: float
    limit_value: float
    order: Order | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        return f"{self.violation_type.value}: {self.message}"


@dataclass
class RiskConfig:
    """Risk management configuration.

    Attributes:
        max_position_value: Maximum position value per asset (in dollars)
        max_position_pct: Maximum position as % of portfolio (0-1)
        max_portfolio_concentration: Maximum single asset concentration (0-1)
        max_daily_loss_pct: Maximum daily loss as % of equity (0-1)
        max_drawdown_pct: Maximum drawdown as % of peak equity (0-1)
        max_symbols: Maximum number of symbols to hold
        min_buying_power_pct: Minimum buying power to maintain (0-1)
        max_order_value: Maximum single order value (in dollars)
        max_order_pct: Maximum single order as % of portfolio (0-1)
        check_pattern_day_trader: Enforce PDT rules
        enabled: Whether risk checks are enabled
    """

    max_position_value: float = 50000.0
    max_position_pct: float = 0.20
    max_portfolio_concentration: float = 0.25
    max_daily_loss_pct: float = 0.02
    max_drawdown_pct: float = 0.10
    max_symbols: int = 20
    min_buying_power_pct: float = 0.10
    max_order_value: float = 25000.0
    max_order_pct: float = 0.10
    check_pattern_day_trader: bool = True
    enabled: bool = True


class RiskManager:
    """Pre-trade risk management and position limits.

    Enforces:
    - Position size limits (absolute and percentage)
    - Portfolio concentration limits
    - Daily loss limits
    - Maximum drawdown circuit breaker
    - Buying power checks
    - Symbol count limits

    Example:
        risk_manager = RiskManager(client, config)

        # Check order before submission
        violations = risk_manager.check_order(order, price=150.0)
        if violations:
            for v in violations:
                print(f"Risk violation: {v}")
        else:
            order_manager.submit_order(order)
    """

    def __init__(
        self,
        client: AlpacaClient,
        config: RiskConfig | None = None,
    ):
        """Initialize the risk manager.

        Args:
            client: Alpaca trading client
            config: Risk configuration (uses defaults if None)
        """
        self._client = client
        self._config = config or RiskConfig()

        # Tracking state
        self._peak_equity: float = 0.0
        self._daily_starting_equity: float = 0.0
        self._daily_reset_date: date | None = None
        self._violations_today: list[RiskViolation] = []

    @property
    def config(self) -> RiskConfig:
        """Get risk configuration."""
        return self._config

    @config.setter
    def config(self, value: RiskConfig) -> None:
        """Set risk configuration."""
        self._config = value

    @property
    def peak_equity(self) -> float:
        """Get peak equity for drawdown calculation."""
        return self._peak_equity

    @property
    def daily_starting_equity(self) -> float:
        """Get starting equity for today."""
        return self._daily_starting_equity

    def initialize(self) -> None:
        """Initialize risk manager state from account.

        Should be called at start of trading session.
        """
        account = self._client.get_account()
        self._update_equity_tracking(account)

        logger.info(
            f"Risk manager initialized",
            extra={
                "equity": account.equity,
                "peak_equity": self._peak_equity,
                "daily_starting_equity": self._daily_starting_equity,
            },
        )

    def _update_equity_tracking(self, account: AccountInfo) -> None:
        """Update equity tracking state.

        Args:
            account: Current account info
        """
        today = date.today()

        # Reset daily tracking if new day
        if self._daily_reset_date != today:
            self._daily_starting_equity = account.equity
            self._daily_reset_date = today
            self._violations_today.clear()

        # Update peak equity
        if account.equity > self._peak_equity:
            self._peak_equity = account.equity

    def check_order(
        self,
        order: Order,
        price: float,
        account: AccountInfo | None = None,
        positions: list[PositionInfo] | None = None,
    ) -> list[RiskViolation]:
        """Check an order against all risk limits.

        Args:
            order: Order to check
            price: Current market price for the asset
            account: Account info (fetched if None)
            positions: Current positions (fetched if None)

        Returns:
            List of risk violations (empty if order passes all checks)
        """
        if not self._config.enabled:
            return []

        violations = []

        # Fetch account and positions if not provided
        if account is None:
            account = self._client.get_account()
        if positions is None:
            positions = self._client.get_positions()

        # Update equity tracking
        self._update_equity_tracking(account)

        order_value = order.quantity * price
        daily_pnl = account.equity - self._daily_starting_equity
        drawdown_pct = ((self._peak_equity - account.equity) / self._peak_equity * 100) if self._peak_equity > 0 else 0.0
        logger.debug(
            "Risk pre-check: equity=$%.2f buying_power=$%.2f positions=%d "
            "daily_pnl=$%.2f drawdown=%.2f%% order=%s %s qty=%.4f value=$%.2f",
            account.equity, account.buying_power, len(positions),
            daily_pnl, drawdown_pct,
            order.side.value, order.symbol, order.quantity, order_value,
        )

        # Check trading blocked
        blocked = self._check_trading_blocked(account)
        if blocked:
            violations.append(blocked)
            return violations  # No point checking further
        logger.debug("trading_blocked check: passed")

        # Check buying power
        bp_violation = self._check_buying_power(order, price, account)
        if bp_violation:
            violations.append(bp_violation)
        else:
            remaining_bp = account.buying_power - order_value
            min_bp = account.equity * self._config.min_buying_power_pct
            logger.debug(
                "buying_power check: order_value=$%.2f remaining_bp=$%.2f min_required=$%.2f passed",
                order_value, remaining_bp, min_bp,
            )

        # Check order size limits
        order_violations = self._check_order_size(order, price, account)
        violations.extend(order_violations)
        if not order_violations:
            order_pct = order_value / account.equity if account.equity > 0 else 1.0
            logger.debug(
                "order_size check: value=$%.2f (max=$%.2f) pct=%.1f%% (max=%.1f%%) passed",
                order_value, self._config.max_order_value,
                order_pct * 100, self._config.max_order_pct * 100,
            )

        # Check position size limits
        position_violations = self._check_position_limits(order, price, account, positions)
        violations.extend(position_violations)
        if not position_violations:
            current_pos = next((p for p in positions if p.symbol == order.symbol), None)
            current_val = abs(current_pos.quantity * price) if current_pos else 0.0
            new_val = current_val + order_value if order.side == OrderSide.BUY else abs(current_val - order_value)
            pos_pct = new_val / account.equity if account.equity > 0 else 1.0
            logger.debug(
                "position_size check: current=$%.2f new=$%.2f (max=$%.2f) pct=%.1f%% (max=%.1f%%) passed",
                current_val, new_val, self._config.max_position_value,
                pos_pct * 100, self._config.max_position_pct * 100,
            )

        # Check portfolio concentration
        concentration = self._check_portfolio_concentration(order, price, account, positions)
        if concentration:
            violations.append(concentration)
        else:
            total_pos_value = sum(abs(p.market_value) for p in positions)
            current_pos = next((p for p in positions if p.symbol == order.symbol), None)
            current_val = abs(current_pos.market_value) if current_pos else 0.0
            if order.side == OrderSide.BUY:
                new_val = current_val + order_value
                new_total = total_pos_value + order_value
            else:
                new_val = max(0, current_val - order_value)
                new_total = max(0, total_pos_value - order_value)
            conc_pct = (new_val / new_total * 100) if new_total > 0 else 0.0
            logger.debug(
                "concentration check: position=$%.2f total=$%.2f concentration=%.1f%% (max=%.1f%%) passed",
                new_val, new_total, conc_pct, self._config.max_portfolio_concentration * 100,
            )

        # Check symbol limits
        symbol_violation = self._check_symbol_limits(order, positions)
        if symbol_violation:
            violations.append(symbol_violation)
        else:
            logger.debug(
                "symbol_limit check: count=%d (max=%d) passed",
                len({p.symbol for p in positions}), self._config.max_symbols,
            )

        # Check daily loss limit
        daily_loss = self._check_daily_loss(account)
        if daily_loss:
            violations.append(daily_loss)
        else:
            daily_loss_pct = (-daily_pnl / self._daily_starting_equity * 100) if daily_pnl < 0 and self._daily_starting_equity > 0 else 0.0
            logger.debug(
                "daily_loss check: loss=%.2f%% (max=%.1f%%) passed",
                daily_loss_pct, self._config.max_daily_loss_pct * 100,
            )

        # Check max drawdown
        drawdown = self._check_max_drawdown(account)
        if drawdown:
            violations.append(drawdown)
        else:
            logger.debug(
                "max_drawdown check: drawdown=%.2f%% (max=%.1f%%) passed",
                drawdown_pct, self._config.max_drawdown_pct * 100,
            )

        # Log violations
        if violations:
            for v in violations:
                self._violations_today.append(v)
                logger.warning(
                    f"Risk violation",
                    extra={
                        "violation_type": v.violation_type.value,
                        "violation_message": v.message,
                        "symbol": order.symbol,
                        "order_quantity": order.quantity,
                    },
                )

        return violations

    def _check_trading_blocked(self, account: AccountInfo) -> RiskViolation | None:
        """Check if trading is blocked."""
        if account.trading_blocked or account.account_blocked:
            return RiskViolation(
                violation_type=RiskViolationType.TRADING_BLOCKED,
                message="Trading is blocked on this account",
                current_value=1.0,
                limit_value=0.0,
            )
        return None

    def _check_buying_power(
        self,
        order: Order,
        price: float,
        account: AccountInfo,
    ) -> RiskViolation | None:
        """Check if order exceeds available buying power."""
        if order.side == OrderSide.SELL:
            return None  # Sells don't use buying power

        order_value = order.quantity * price
        required_buying_power = order_value  # Simplified; margin accounts would differ

        if required_buying_power > account.buying_power:
            return RiskViolation(
                violation_type=RiskViolationType.BUYING_POWER,
                message=f"Order value ${order_value:,.2f} exceeds buying power ${account.buying_power:,.2f}",
                current_value=required_buying_power,
                limit_value=account.buying_power,
                order=order,
            )

        # Check minimum buying power threshold
        remaining_bp = account.buying_power - required_buying_power
        min_required_bp = account.equity * self._config.min_buying_power_pct

        if remaining_bp < min_required_bp:
            return RiskViolation(
                violation_type=RiskViolationType.BUYING_POWER,
                message=f"Order would reduce buying power below minimum ${min_required_bp:,.2f}",
                current_value=remaining_bp,
                limit_value=min_required_bp,
                order=order,
            )

        return None

    def _check_order_size(
        self,
        order: Order,
        price: float,
        account: AccountInfo,
    ) -> list[RiskViolation]:
        """Check order size limits."""
        violations = []
        order_value = order.quantity * price

        # Check absolute order size
        if order_value > self._config.max_order_value:
            violations.append(
                RiskViolation(
                    violation_type=RiskViolationType.ORDER_SIZE,
                    message=f"Order value ${order_value:,.2f} exceeds max ${self._config.max_order_value:,.2f}",
                    current_value=order_value,
                    limit_value=self._config.max_order_value,
                    order=order,
                )
            )

        # Check order as % of portfolio
        order_pct = order_value / account.equity if account.equity > 0 else 1.0
        if order_pct > self._config.max_order_pct:
            violations.append(
                RiskViolation(
                    violation_type=RiskViolationType.ORDER_SIZE,
                    message=f"Order is {order_pct:.1%} of portfolio, max is {self._config.max_order_pct:.1%}",
                    current_value=order_pct,
                    limit_value=self._config.max_order_pct,
                    order=order,
                )
            )

        return violations

    def _check_position_limits(
        self,
        order: Order,
        price: float,
        account: AccountInfo,
        positions: list[PositionInfo],
    ) -> list[RiskViolation]:
        """Check position size limits."""
        violations = []

        # Find current position for this symbol
        current_position = next(
            (p for p in positions if p.symbol == order.symbol),
            None,
        )
        current_qty = current_position.quantity if current_position else 0.0
        current_value = abs(current_qty * price)

        # Calculate new position after order
        if order.side == OrderSide.BUY:
            new_qty = current_qty + order.quantity
        else:
            new_qty = current_qty - order.quantity

        new_value = abs(new_qty * price)

        # Check absolute position value
        if new_value > self._config.max_position_value:
            violations.append(
                RiskViolation(
                    violation_type=RiskViolationType.POSITION_SIZE,
                    message=f"Position would be ${new_value:,.2f}, max is ${self._config.max_position_value:,.2f}",
                    current_value=new_value,
                    limit_value=self._config.max_position_value,
                    order=order,
                )
            )

        # Check position as % of portfolio
        position_pct = new_value / account.equity if account.equity > 0 else 1.0
        if position_pct > self._config.max_position_pct:
            violations.append(
                RiskViolation(
                    violation_type=RiskViolationType.POSITION_SIZE,
                    message=f"Position would be {position_pct:.1%} of portfolio, max is {self._config.max_position_pct:.1%}",
                    current_value=position_pct,
                    limit_value=self._config.max_position_pct,
                    order=order,
                )
            )

        return violations

    def _check_portfolio_concentration(
        self,
        order: Order,
        price: float,
        account: AccountInfo,
        positions: list[PositionInfo],
    ) -> RiskViolation | None:
        """Check portfolio concentration limits."""
        # Calculate total portfolio value
        total_value = sum(abs(p.market_value) for p in positions)

        # Calculate position value after order
        current_position = next(
            (p for p in positions if p.symbol == order.symbol),
            None,
        )
        current_value = abs(current_position.market_value) if current_position else 0.0

        order_value = order.quantity * price
        if order.side == OrderSide.BUY:
            new_value = current_value + order_value
            new_total = total_value + order_value
        else:
            new_value = max(0, current_value - order_value)
            new_total = max(0, total_value - order_value)

        if new_total > 0:
            concentration = new_value / new_total
            if concentration > self._config.max_portfolio_concentration:
                return RiskViolation(
                    violation_type=RiskViolationType.PORTFOLIO_CONCENTRATION,
                    message=f"Position would be {concentration:.1%} of portfolio, max is {self._config.max_portfolio_concentration:.1%}",
                    current_value=concentration,
                    limit_value=self._config.max_portfolio_concentration,
                    order=order,
                )

        return None

    def _check_symbol_limits(
        self,
        order: Order,
        positions: list[PositionInfo],
    ) -> RiskViolation | None:
        """Check symbol count limits."""
        if order.side == OrderSide.SELL:
            return None  # Sells don't add symbols

        # Check if this is a new symbol
        current_symbols = {p.symbol for p in positions}
        if order.symbol not in current_symbols:
            if len(current_symbols) >= self._config.max_symbols:
                return RiskViolation(
                    violation_type=RiskViolationType.SYMBOL_LIMIT,
                    message=f"Already holding {len(current_symbols)} symbols, max is {self._config.max_symbols}",
                    current_value=len(current_symbols),
                    limit_value=self._config.max_symbols,
                    order=order,
                )

        return None

    def _check_daily_loss(self, account: AccountInfo) -> RiskViolation | None:
        """Check daily loss limit."""
        if self._daily_starting_equity <= 0:
            return None

        daily_pnl = account.equity - self._daily_starting_equity
        daily_loss_pct = -daily_pnl / self._daily_starting_equity if daily_pnl < 0 else 0.0

        if daily_loss_pct > self._config.max_daily_loss_pct:
            return RiskViolation(
                violation_type=RiskViolationType.DAILY_LOSS,
                message=f"Daily loss is {daily_loss_pct:.1%}, max is {self._config.max_daily_loss_pct:.1%}. Trading halted.",
                current_value=daily_loss_pct,
                limit_value=self._config.max_daily_loss_pct,
            )

        return None

    def _check_max_drawdown(self, account: AccountInfo) -> RiskViolation | None:
        """Check maximum drawdown circuit breaker."""
        if self._peak_equity <= 0:
            return None

        drawdown = (self._peak_equity - account.equity) / self._peak_equity

        if drawdown > self._config.max_drawdown_pct:
            return RiskViolation(
                violation_type=RiskViolationType.MAX_DRAWDOWN,
                message=f"Drawdown is {drawdown:.1%}, max is {self._config.max_drawdown_pct:.1%}. Circuit breaker triggered.",
                current_value=drawdown,
                limit_value=self._config.max_drawdown_pct,
            )

        return None

    def get_available_capacity(
        self,
        symbol: str,
        price: float,
        account: AccountInfo | None = None,
        positions: list[PositionInfo] | None = None,
    ) -> float:
        """Get available capacity for a position (in dollars).

        Args:
            symbol: Asset symbol
            price: Current price
            account: Account info (fetched if None)
            positions: Current positions (fetched if None)

        Returns:
            Maximum additional position value allowed
        """
        if account is None:
            account = self._client.get_account()
        if positions is None:
            positions = self._client.get_positions()

        # Current position
        current_position = next(
            (p for p in positions if p.symbol == symbol),
            None,
        )
        current_value = abs(current_position.market_value) if current_position else 0.0

        # Limits
        max_by_position_value = self._config.max_position_value - current_value
        max_by_position_pct = (self._config.max_position_pct * account.equity) - current_value
        max_by_order_value = self._config.max_order_value
        max_by_order_pct = self._config.max_order_pct * account.equity
        max_by_buying_power = account.buying_power - (self._config.min_buying_power_pct * account.equity)

        # Most restrictive limit
        available = min(
            max_by_position_value,
            max_by_position_pct,
            max_by_order_value,
            max_by_order_pct,
            max_by_buying_power,
        )

        return max(0.0, available)

    def is_trading_allowed(self, account: AccountInfo | None = None) -> tuple[bool, str]:
        """Check if trading is currently allowed.

        Args:
            account: Account info (fetched if None)

        Returns:
            Tuple of (allowed, reason)
        """
        if account is None:
            account = self._client.get_account()

        self._update_equity_tracking(account)

        # Check trading blocked
        if account.trading_blocked or account.account_blocked:
            return False, "Account trading is blocked"

        # Check daily loss
        daily_violation = self._check_daily_loss(account)
        if daily_violation:
            return False, daily_violation.message

        # Check drawdown
        drawdown_violation = self._check_max_drawdown(account)
        if drawdown_violation:
            return False, drawdown_violation.message

        return True, "Trading allowed"

    def get_risk_summary(
        self,
        account: AccountInfo | None = None,
        positions: list[PositionInfo] | None = None,
    ) -> dict[str, Any]:
        """Get a summary of current risk metrics.

        Args:
            account: Account info (fetched if None)
            positions: Current positions (fetched if None)

        Returns:
            Dictionary with risk metrics
        """
        if account is None:
            account = self._client.get_account()
        if positions is None:
            positions = self._client.get_positions()

        self._update_equity_tracking(account)

        # Calculate metrics
        daily_pnl = account.equity - self._daily_starting_equity
        daily_return = daily_pnl / self._daily_starting_equity if self._daily_starting_equity > 0 else 0.0

        drawdown = (self._peak_equity - account.equity) / self._peak_equity if self._peak_equity > 0 else 0.0

        total_position_value = sum(abs(p.market_value) for p in positions)
        largest_position = max(
            (abs(p.market_value) for p in positions),
            default=0.0,
        )

        return {
            "equity": account.equity,
            "buying_power": account.buying_power,
            "daily_pnl": daily_pnl,
            "daily_return_pct": daily_return * 100,
            "peak_equity": self._peak_equity,
            "drawdown_pct": drawdown * 100,
            "position_count": len(positions),
            "total_position_value": total_position_value,
            "largest_position_value": largest_position,
            "largest_position_pct": (largest_position / account.equity * 100) if account.equity > 0 else 0,
            "violations_today": len(self._violations_today),
            "limits": {
                "max_position_value": self._config.max_position_value,
                "max_position_pct": self._config.max_position_pct * 100,
                "max_daily_loss_pct": self._config.max_daily_loss_pct * 100,
                "max_drawdown_pct": self._config.max_drawdown_pct * 100,
                "max_symbols": self._config.max_symbols,
            },
        }
